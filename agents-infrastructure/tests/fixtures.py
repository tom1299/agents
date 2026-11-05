import logging
import time

from pytest import fixture, skip

from kubernetes import config, client

config.load_kube_config()
core = client.CoreV1Api()
networking = client.NetworkingV1Api()

def get_ingress_ip_v4(ingress_name: str, namespace: str) -> str:
    try:
        config.load_kube_config()
        ingress = networking.read_namespaced_ingress(name=ingress_name, namespace=namespace)
        ip = ingress.status.load_balancer.ingress[0].ip
        return ip
    except Exception as exc:
        raise RuntimeError(f"Failed to get ingress IP for {ingress_name} in namespace {namespace}: {exc}")

def wait_for_container_waiting_reason(ns: str, pod: str, reasons: set[str], timeout: int = 60) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        statuses = core.read_namespaced_pod(pod, ns).status.container_statuses or []
        for status in statuses:
            waiting = status.state.waiting
            if waiting and waiting.reason in reasons:
                return waiting.reason
        time.sleep(1)
    raise TimeoutError(f"{ns}/{pod} did not reach any of {reasons} within {timeout}s")

@fixture
def kubernetes_mcp_server_ip() -> str:
    try:
        return get_ingress_ip_v4(ingress_name="kubernetes-mcp-server", namespace="kubernetes-mcp-server")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture
def flux_operator_mcp_server_ip() -> str:
    try:
        return get_ingress_ip_v4(ingress_name="flux-operator-mcp", namespace="flux-system")
    except Exception as exc:
        skip(f"Kubernetes cluster not reachable: {exc}")

@fixture
def create_temp_namespace():
    created: list[str] = []

    def _create(ns_name: str) -> str:
        core.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name=ns_name)))
        created.append(ns_name)
        return ns_name

    # Returns function to create ns
    yield _create

    # Runs on tear down, deletes ns
    for ns_to_delete in reversed(created):
        core.delete_namespace(ns_to_delete)

@fixture
def create_pod_with_faulty_image(create_temp_namespace):
    created_pods: list[client.V1Pod] = []

    def _create(ns_name: str, pod_name: str) -> tuple[str, str]:
        create_temp_namespace(ns_name)
        pod_manifest = client.V1Pod(
            metadata=client.V1ObjectMeta(name=pod_name),
            spec=client.V1PodSpec(
                containers=[client.V1Container(name="nginx", image="nignx:latest")]
            )
        )
        core.create_namespaced_pod(namespace=ns_name, body=pod_manifest)
        wait_for_container_waiting_reason(ns_name, pod_name, {"ErrImagePull", "ImagePullBackOff"})
        created_pods.append(pod_manifest)
        return ns_name, pod_name

    # Returns function to create pod
    yield _create

    # Runs on tear down, deletes pods and namespaces
    for pod_to_delete in reversed(created_pods):
        try:
            core.delete_namespaced_pod(name=pod_to_delete.metadata.name, namespace=pod_to_delete.metadata.namespace)
        except Exception as exc:
            logging.warning(f"Failed to delete pod {pod_to_delete} in namespace {pod_to_delete.metadata.namespace}: {exc}")
