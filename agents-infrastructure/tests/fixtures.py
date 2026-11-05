from pytest import fixture, skip

from kubernetes import config, client

def get_ingress_ip_v4(ingress_name: str, namespace: str) -> str:
    try:
        config.load_kube_config()
        v1 = client.NetworkingV1Api()
        ingress = v1.read_namespaced_ingress(name=ingress_name, namespace=namespace)
        ip = ingress.status.load_balancer.ingress[0].ip
        return ip
    except Exception as exc:
        raise RuntimeError(f"Failed to get ingress IP for {ingress_name} in namespace {namespace}: {exc}")

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