# TODO: Rename to something more expressive
from fastmcp import Client
from fastmcp.client import StreamableHttpTransport

from agents_infrastructure.agents.analysis_agents import AnalysisAgent


class BaseTestClass:
    async def create_agent(self, model_name: str, system_prompt: str, tools=None, middleware=None) -> AnalysisAgent:
        if middleware is None:
            middleware = []
        if tools is None:
            tools = []

        agent: AnalysisAgent = AnalysisAgent()
        agent.tools = tools
        agent.middleware = middleware
        agent.model = model_name
        agent.system_prompt = system_prompt
        agent.create_analysis_agent()
        return agent

    async def get_kubernetes_mcp_server(self, kubernetes_mcp_server_ip: str) -> Client[StreamableHttpTransport]:
        transport = StreamableHttpTransport(
            url=f"http://{kubernetes_mcp_server_ip}/mcp",
            headers={
                "Host": "kubernetes-mcp-server"
            }
        )
        client = Client(transport)
        return client

    async def get_flux_operator_mcp_server(self, flux_operator_mcp_server_ip: str) -> Client[StreamableHttpTransport]:
        transport = StreamableHttpTransport(
            url=f"http://{flux_operator_mcp_server_ip}/mcp",
            headers={
                "Host": "flux-operator-mcp"
            }
        )
        client = Client(transport)
        return client