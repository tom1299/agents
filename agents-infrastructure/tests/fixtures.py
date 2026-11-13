import logging
import time
import yaml
from pathlib import Path

from langchain.chat_models import init_chat_model
from pytest import fixture, skip

from kubernetes import config, client, dynamic

TEST_MANIFESTS_DIR = Path(__file__).parent / "test-manifests"

def get_ingress_ip_v4(networking_client: client.NetworkingV1Api, ingress_name: str, namespace: str) -> str:
    try:
        config.load_kube_config()
        ingress = networking_client.read_namespaced_ingress(name=ingress_name, namespace=namespace)
        ip = ingress.status.load_balancer.ingress[0].ip
        return ip
    except Exception as exc:
        raise RuntimeError(f"Failed to get ingress IP for {ingress_name} in namespace {namespace}: {exc}")

def wait_for_container_waiting_reason(core_client: client.CoreV1Api, ns: str, pod: str, reasons: set[str], timeout: int = 60) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core_client.read_namespaced_pod(pod, ns).status.container_statuses or []
        for status in statuses:
            waiting = status.state.waiting
            if waiting and waiting.reason in reasons:
                return waiting.reason
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod} did not reach any of {reasons} within {timeout}s")

def wait_for_deployment_replicas_ready(apps_client: client.AppsV1Api, ns: str, deployment: str, expected_replicas: int, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        dep = apps_client.read_namespaced_deployment(deployment, ns)
        if dep.status.ready_replicas == expected_replicas:
            return
        time.sleep(1)
    raise TimeoutError(f"{ns}/{deployment} did not have {expected_replicas} ready replicas within {timeout}s")

def wait_for_pods_running(core_client: client.CoreV1Api, ns: str, label_selector: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pods = core_client.list_namespaced_pod(ns, label_selector=label_selector).items
        if pods and all(pod.status.phase == "Running" for pod in pods):
            return
        time.sleep(1)
    raise TimeoutError(f"Not all pods in namespace {ns} with label selector {label_selector} are running within {timeout}s")

def wait_for_pod_deletion(core_client: client.CoreV1Api, ns: str, label_selector: str, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pods = core_client.list_namespaced_pod(ns, label_selector=label_selector).items
        if not pods:
            return
        time.sleep(1)
    raise TimeoutError(f"Pods in namespace {ns} with label selector {label_selector} were not deleted within {timeout}s")

def load_kube_config_or_skip() -> None:
    try:
        config.load_kube_config()
    except Exception as exc:
        skip(f"Kubernetes config not available: {exc}")

@fixture
def create_model():
    def _create(model_name: str):
        kwargs = {}
        # TODO: This is a temporary workaround for the fact that tools + reasoning are not supported on chat completions. Once this is fixed, we can remove this.
        if model_name.startswith("openai:"):
            kwargs["reasoning_effort"] = "none"  # tools + reasoning unsupported on chat completions
        return init_chat_model(model_name, **kwargs)
    return _create

@fixture
def k8s_core_client() -> client.CoreV1Api:
    load_kube_config_or_skip()
    return client.CoreV1Api()

@fixture
def k8s_apps_client() -> client.AppsV1Api:
    load_kube_config_or_skip()
    return client.AppsV1Api()

@fixture
def k8s_networking_client() -> client.NetworkingV1Api:
    load_kube_config_or_skip()
    return client.NetworkingV1Api()

@fixture
def k8s_dynamic_client() -> dynamic.DynamicClient:
    load_kube_config_or_skip()
    k8s_client = client.ApiClient()
    return dynamic.DynamicClient(k8s_client)

@fixture
def kubernetes_mcp_server_ip(k8s_networking_client) -> str:
    try:
        return get_ingress_ip_v4(k8s_networking_client, ingress_name="kubernetes-mcp-server", namespace="kubernetes-mcp-server")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture
def flux_operator_mcp_server_ip(k8s_networking_client) -> str:
    try:
        return get_ingress_ip_v4(k8s_networking_client, ingress_name="flux-operator-mcp", namespace="flux-system")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture
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

@fixture
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

@fixture
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

@fixture
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
