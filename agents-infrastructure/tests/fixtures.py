import logging
import time

from pytest import fixture, skip

from kubernetes import config, client

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

def load_kube_config_or_skip() -> None:
    try:
        config.load_kube_config()
    except Exception as exc:
        skip(f"Kubernetes config not available: {exc}")

@fixture
def k8s_core_client() -> client.CoreV1Api:
    load_kube_config_or_skip()
    return client.CoreV1Api()

@fixture
def k8s_networking_client() -> client.NetworkingV1Api:
    load_kube_config_or_skip()
    return client.NetworkingV1Api()

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
