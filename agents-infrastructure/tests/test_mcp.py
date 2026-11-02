from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from kubernetes import config, client
from langchain.mcp import MCPAdapter
from pytest import mark, fixture

@fixture
def kubernetes_mcp_server_ip() -> str:
    # TODO: Move to init of package, get name and namespace from config
    config.load_kube_config()
    v1 = client.NetworkingV1Api()
    ingress = v1.read_namespaced_ingress(name="kubernetes-mcp-server", namespace="kubernetes-mcp-server")
    ip = ingress.status.load_balancer.ingress[0].ip
    return ip

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