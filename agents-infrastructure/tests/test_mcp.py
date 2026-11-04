from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from kubernetes import config, client
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool
from pytest import mark, fixture, skip

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

def contains_metadata_annotation(tool: BaseTool, annotation: str) -> bool:
    annotations = (tool.metadata or {}).get("mcp", {}).get("tool", {}).get("annotations", {})
    annotation_value = annotations.get(annotation)
    return annotation_value is not None and annotation_value == True


def read_only(tool: BaseTool) -> bool:
    read_only = contains_metadata_annotation(tool, "read_only_hint")
    destructive = contains_metadata_annotation(tool, "destructive_hint")
    return read_only and not destructive

class TestMcp():

    @mark.asyncio
    async  def test_kubernetes_mcp_server(self, kubernetes_mcp_server_ip: str) -> None:

        transport = StreamableHttpTransport(
            url=f"http://{kubernetes_mcp_server_ip}/mcp",
            headers={
                "Host": "kubernetes-mcp-server"
            }
        )
        client = Client(transport)

        async with MCPAdapter(client) as adapter:
            tools = await adapter.list_tools()
            assert len(tools) > 0, "Expected at least one tool to be available from the MCP server."

    @mark.asyncio
    async def test_flux_operator_mcp_server(self, flux_operator_mcp_server_ip: str) -> None:

        transport = StreamableHttpTransport(
            url=f"http://{flux_operator_mcp_server_ip}/mcp",
            headers={
                "Host": "flux-operator-mcp"
            }
        )
        client = Client(transport)

        async with MCPAdapter(client) as adapter:
            tools = await adapter.list_tools()
            assert len(tools) == 17, (f"Expected 17 tools to be available from the flux-operator MCP server,"
                                      f"but found {len(tools)}.")

    @mark.asyncio
    async def test_filter_read_only(self, flux_operator_mcp_server_ip: str) -> None:

        transport = StreamableHttpTransport(
            url=f"http://{flux_operator_mcp_server_ip}/mcp",
            headers={
                "Host": "flux-operator-mcp"
            }
        )
        client = Client(transport)

        async with MCPAdapter(client) as adapter:
            tools = await adapter.list_tools()
            read_only_tools = list(filter(read_only, tools))

            assert len(read_only_tools) == 10, f"Expected 10 read-only tools, but found {len(read_only_tools)}."
            for tool in read_only_tools:
                assert read_only(tool), f"Tool {tool.name} is not read-only as expected."

