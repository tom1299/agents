from collections.abc import Callable, Awaitable
from typing import Any

from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from langchain.agents.middleware import AgentMiddleware
from langchain.mcp import MCPAdapter
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command
from pytest import mark, raises

from agents_infrastructure.agents.analysis_agent import K8sAnalysisAgent, Classification, Label, AnalysisResult
from agents_infrastructure.utils import read_only

class ToolMonitoringMiddleware(AgentMiddleware):

    tool_invocations: int = 0

    max_tool_invocations: int

    def __init__(self, max_tool_invocations: int) -> None:
        self.max_tool_invocations = max_tool_invocations

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:

        self.tool_invocations += 1
        if self.tool_invocations > self.max_tool_invocations:
            raise Exception(f"Exceeded maximum tool invocations: {self.max_tool_invocations}")
        try:
            result = await handler(request)
            print("Tool completed successfully")
            return result
        except Exception as e:
            raise

class TestAnalystAgent():

    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-4o-mini"])
    async def test_pod_failure_analysis(self, kubernetes_mcp_server_ip: str, create_pod_with_faulty_image, model_name: str) -> None:

        ns = "test-pod-failure-analysis"
        create_pod_with_faulty_image(ns, "faulty-pod")

        client = await self.get_kubernetes_mcp_server(kubernetes_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))

            system_prompt = (f"You are a Kubernetes analysis agent. "
                             f"You analyze problems and provide insights and "
                             f"recommendations for resolution of given problems statements. "
                             f"The provided tools connect you to the Kubernetes cluster "
                             f"and allow you to gather information about resources."
                             f"Your response must be in the format of the AnalysisResult model."
                             f"For labels of your response use"
                             f"{Label.__args__} and for classification use {Classification.__args__}."
                             )
            max_invocation_middleware = ToolMonitoringMiddleware(max_tool_invocations=3)

            agent = await self.create_agent(model_name, system_prompt, tools, [max_invocation_middleware])
            prompt = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"There is a pod failing in the the namespace {ns}\n"
                            f"Analyze the pod failure and provide a summary, reason,"
                            f"recommended fix, classification and labels."
                        ),
                    }
                ]
            }

            with raises(Exception, match="Exceeded maximum tool invocations"):
                await agent.agent.ainvoke(prompt)

            # analysis: AnalysisResult = response["structured_response"]
            #
            # assert analysis.classification == "image_pull_error"
            # assert set(analysis.labels) == {"pod", "image"}

    async def create_agent(self, model_name: str, system_prompt: str, tools=None, middleware=None) -> K8sAnalysisAgent:
        if middleware is None:
            middleware = []
        if tools is None:
            tools = []

        agent: K8sAnalysisAgent = K8sAnalysisAgent()
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
