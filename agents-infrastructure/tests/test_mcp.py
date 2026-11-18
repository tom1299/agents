from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from langchain.mcp import MCPAdapter
from pytest import mark

from agents_infrastructure.utils import read_only


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

    @mark.asyncio
    async def test_kubernetes_mcp_server_permissions(self, kubernetes_mcp_server_ip: str, create_pod_with_image, bind_cluster_role_to_sa) -> None:

        transport = StreamableHttpTransport(
            url=f"http://{kubernetes_mcp_server_ip}/mcp",
            headers={
                "Host": "kubernetes-mcp-server"
            }
        )
        client = Client(transport)

        async with MCPAdapter(client) as adapter:
            tools = await adapter.list_tools()
            exec_in_pod_tool = next((tool for tool in tools if tool.name == "pods_exec"), None)
            assert exec_in_pod_tool

            namespace, pod_name = create_pod_with_image("test-permissions", "test-pod", "nginx:latest")
            bind_cluster_role_to_sa("kubernetes-mcp-server", "kubernetes-mcp-server", namespace, "edit")
            result = await exec_in_pod_tool.ainvoke({
                "name": pod_name,
                "namespace": namespace,
                "command": ["echo", "Hello, World!"]
            })
            assert result[0]['text'] == "Hello, World!"
