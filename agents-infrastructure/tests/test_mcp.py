from langchain.mcp import MCPAdapter
from pytest import mark

class TestMcp():

    @mark.asyncio
    async  def test_kubernetes_mcp_server(self) -> None:
        # TODO: Lookup actual ip
        async with MCPAdapter("http://172.18.0.4/mcp") as adapter:
            tools = await adapter.list_tools()
            # TODO: Make better assert
            assert len(tools) > 0, "Expected at least one tool to be available from the MCP server."