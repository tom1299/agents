import logging
import time

import yaml
from pathlib import Path

from langchain.chat_models import init_chat_model
from pytest import fixture, skip

from kubernetes import client, dynamic, config
from kubernetes.dynamic.exceptions import NotFoundError
from kubernetes.client.rest import ApiException

from agents_infrastructure.k8s_functions import get_ingress_ip_v4, wait_for_container_waiting_reason, \
    wait_for_deployment_replicas_ready, wait_for_pods_running, wait_for_pod_deletion

TEST_MANIFESTS_DIR = Path(__file__).parent / "test-manifests"

def load_kube_config_or_skip() -> None:
    try:
        config.load_kube_config()
    except Exception as exc:
        skip(f"Kubernetes config not available: {exc}")

@fixture(scope="module")
def create_model():
    def _create(model_name: str):
        kwargs = {}
        # # TODO: This is a temporary workaround for the fact that tools + reasoning are not supported on chat completions. Once this is fixed, we can remove this.
        if model_name.startswith("openai:"):
            kwargs["reasoning"] = {"effort": "high", "summary": "auto"}  # tools + reasoning unsupported on chat completions
        return init_chat_model(model_name, **kwargs)
    return _create

@fixture(scope="module")
def k8s_api_client():
    load_kube_config_or_skip()
    with client.ApiClient() as api_client:
        yield api_client

@fixture(scope="module")
def k8s_core_client() -> client.CoreV1Api:
    load_kube_config_or_skip()
    return client.CoreV1Api()

@fixture(scope="module")
def k8s_apps_client() -> client.AppsV1Api:
    load_kube_config_or_skip()
    return client.AppsV1Api()

@fixture(scope="module")
def k8s_networking_client() -> client.NetworkingV1Api:
    load_kube_config_or_skip()
    return client.NetworkingV1Api()

@fixture(scope="module")
def k8s_dynamic_client() -> dynamic.DynamicClient:
    load_kube_config_or_skip()
    k8s_client = client.ApiClient()
    return dynamic.DynamicClient(k8s_client)

@fixture(scope="module")
def kubernetes_mcp_server_ip(k8s_networking_client) -> str:
    try:
        return get_ingress_ip_v4(k8s_networking_client, ingress_name="kubernetes-mcp-server", namespace="kubernetes-mcp-server")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture(scope="module")
def flux_operator_mcp_server_ip(k8s_networking_client) -> str:
    try:
        return get_ingress_ip_v4(k8s_networking_client, ingress_name="flux-operator-mcp", namespace="flux-system")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture(scope="module")
def create_temp_namespace(k8s_core_client):
    created: list[str] = []

    def _create(ns_name: str) -> str:
        k8s_core_client.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=ns_name)))
        created.append(ns_name)
        return ns_name

    # Returns function to create ns
    yield _create

    # Runs on tear down, deletes ns
    for ns_to_delete in reversed(created):
        k8s_core_client.delete_namespace(ns_to_delete)

@fixture(scope="module")
def create_pod_with_faulty_image(k8s_core_client, create_temp_namespace):
    created_pods: list[client.V1Pod] = []

    def _create(ns_name: str, pod_name: str) -> tuple[str, str]:
        create_temp_namespace(ns_name)
        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(
                containers=[client.V1Container(name="nginx", image="nignx:latest")]
            )
        )
        k8s_core_client.create_namespaced_pod(namespace=ns_name, body=pod_manifest)
        wait_for_container_waiting_reason(k8s_core_client, ns_name, pod_name, {"ErrImagePull", "ImagePullBackOff"})
        created_pods.append(pod_manifest)
        return ns_name, pod_name

    # Returns function to create pod
    yield _create

    # Runs on tear down, deletes pods and namespaces
    for pod_to_delete in reversed(created_pods):
        try:
            k8s_core_client.delete_namespaced_pod(name=pod_to_delete.metadata.name, namespace=pod_to_delete.metadata.namespace)
        except Exception as exc:
            logging.warning(f"Failed to delete pod {pod_to_delete} in namespace {pod_to_delete.metadata.namespace}: {exc}")

# TODO: Create a generic fixture for creating pods with conditions for waiting.
@fixture(scope="module")
def create_pod_with_image(k8s_core_client, create_temp_namespace):
    created_pods: list[client.V1Pod] = []

    def _create(ns_name: str, pod_name: str, image: str = "nginx:latest") -> tuple[str, str]:
        create_temp_namespace(ns_name)
        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(name=pod_name, labels={"kubernetes.io/name": pod_name}),
            spec=client.V1PodSpec(
                containers=[client.V1Container(name="main", image=image)]
            )
        )
        k8s_core_client.create_namespaced_pod(namespace=ns_name, body=pod_manifest)
        wait_for_pods_running(k8s_core_client, ns_name, label_selector=f"kubernetes.io/name={pod_name}", timeout=60)
        created_pods.append(pod_manifest)
        return ns_name, pod_name

    # Returns function to create pod
    yield _create

    # Runs on tear down, deletes pods and namespaces
    for pod_to_delete in reversed(created_pods):
        try:
            k8s_core_client.delete_namespaced_pod(name=pod_to_delete.metadata.name, namespace=pod_to_delete.metadata.namespace)
            wait_for_pod_deletion(k8s_core_client, ns=pod_to_delete.metadata.namespace, label_selector=f"kubernetes.io/name={pod_to_delete.metadata.name}", timeout=60)
        except Exception as exc:
            logging.warning(f"Failed to delete pod {pod_to_delete} in namespace {pod_to_delete.metadata.namespace}: {exc}")


@fixture(scope="module")
def create_deployment_failing_due_to_affinity(k8s_apps_client, create_temp_namespace):
    created_deployments: list[tuple[str, str]] = []

    def _create(ns_name: str, deployment_name: str) -> tuple[str, str]:
        create_temp_namespace(ns_name)
        with open(TEST_MANIFESTS_DIR / "deployment-failing-due-to-affinity.yaml", "r") as f:
            deployment_manifest = yaml.safe_load(f)
        deployment_manifest["metadata"]["name"] = deployment_name
        k8s_apps_client.create_namespaced_deployment(namespace=ns_name, body=deployment_manifest)
        wait_for_deployment_replicas_ready(k8s_apps_client, ns_name, deployment_name, expected_replicas=1)
        created_deployments.append((ns_name, deployment_name))
        return ns_name, deployment_name

    # Returns function to create deployment
    yield _create

    # Runs on tear down, deletes deployments and namespaces
    for ns_to_delete, deployment_to_delete in reversed(created_deployments):
        try:
            k8s_apps_client.delete_namespaced_deployment(name=deployment_to_delete, namespace=ns_to_delete)
        except Exception as exc:
            logging.warning(f"Failed to delete deployment {deployment_to_delete} in namespace {ns_to_delete}: {exc}")

@fixture(scope="module")
def create_flux_instance(k8s_dynamic_client, k8s_core_client) :

    flux_api = k8s_dynamic_client.resources.get(api_version='fluxcd.controlplane.io/v1', kind='FluxInstance')

    def _create(instance_manifest: str) -> None:
        with open(TEST_MANIFESTS_DIR / instance_manifest, "r") as f:
            flux_manifest = yaml.safe_load(f)

        flux_api.create(namespace="flux-system", body=flux_manifest)

        wait_for_pods_running(k8s_core_client, ns="flux-system", label_selector="app.kubernetes.io/part-of=flux", timeout=120)

    # Returns function to create flux instance
    yield _create

    # Runs on tear down, deletes instances and namespaces
    try:
        flux_api.delete(name="flux", namespace="flux-system")
        wait_for_pod_deletion(k8s_core_client, ns="flux-system", label_selector="app.kubernetes.io/part-of=flux", timeout=120)
    except Exception as exc:
        logging.warning(f"Failed to delete flux instance flux in namespace flux-system: {exc}")

@fixture(scope="module")
def apply_manifest(k8s_api_client, create_temp_namespace):
    dynamic_client = dynamic.DynamicClient(k8s_api_client)
    applied = []

    def _apply(manifest: str, namespace: str) -> None:
        create_temp_namespace(namespace)
        with open(TEST_MANIFESTS_DIR / manifest, "r") as manifest_file:
            documents = [document for document in yaml.safe_load_all(manifest_file) if document is not None]
        if not documents:
            raise ValueError(f"No resources in manifest: {manifest}")

        resources = []
        for document in documents:
            resource = dynamic_client.resources.get(
                api_version=document["apiVersion"], kind=document["kind"]
            )
            metadata = document["metadata"]
            if not resource.namespaced:
                raise ValueError(f"Cluster-scoped resource not supported: {document['kind']}")
            if metadata.get("namespace", namespace) != namespace:
                raise ValueError(f"Namespace mismatch for {document['kind']}/{metadata['name']}")
            resources.append((resource, document, metadata["name"]))

        for resource, document, name in resources:
            applied.append((resource, name, namespace))
            resource.server_side_apply(
                body=document, namespace=namespace, field_manager="python-client"
            )

    yield _apply

    errors = []
    for resource, name, namespace in reversed(applied):
        try:
            resource.delete(name=name, namespace=namespace)
        except NotFoundError:
            continue
        except ApiException as exc:
            errors.append(exc)
    if errors:
        raise Exception(f"Failed to delete manifest resources: {errors}")

@fixture(scope="module")
def bind_cluster_role_to_sa(k8s_dynamic_client):

    role_bindings_api = k8s_dynamic_client.resources.get(
        api_version="rbac.authorization.k8s.io/v1",
        kind="RoleBinding",
    )

    create_binding: tuple[str, str]
    def _create(sa_name, sa_ns, target_ns, cluster_role_name):
        nonlocal create_binding
        created_binding = f"{sa_name}-to-{cluster_role_name}-binding"

        role_bindings_api.create(
            namespace=target_ns,
            body={
                "apiVersion": "rbac.authorization.k8s.io/v1",
                "kind": "RoleBinding",
                "metadata": {
                    "name": created_binding,
                    "namespace": target_ns
                },
                "roleRef": {
                    "apiGroup": "rbac.authorization.k8s.io",
                    "kind": "ClusterRole",
                    "name": cluster_role_name,
                },
                "subjects": [{
                    "kind": "ServiceAccount",
                    "name": sa_name,
                    "namespace": sa_ns,
                }],
            },
        )
        create_binding = (created_binding, target_ns)

        # TODO Create equivalent kubectl auth can-i check
        # instead of sleep
        time.sleep(0.5)  # Wait for RBAC propagation

    yield _create

    # Runs on tear down, deletes role binding
    if create_binding:
        binding_name, target_ns = create_binding
        try:
            role_bindings_api.delete(name=binding_name, namespace=target_ns)
        except Exception as exc:
            logging.warning(f"Failed to delete role binding {binding_name} in namespace {target_ns}: {exc}")