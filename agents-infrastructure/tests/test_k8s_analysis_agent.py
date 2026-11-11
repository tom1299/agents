import re

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
from tests import prompts


LABEL_SELECTOR_PATTERN = re.compile(r"^([a-zA-Z0-9](?:[\w.\-]{0,61}[a-zA-Z0-9])?)=([a-zA-Z0-9](?:[\w.\-]{0,61}[a-zA-Z0-9])?)?$")

class ToolCallValidationMiddleware(AgentMiddleware):

    tool_invocations: int = 0

    max_tool_invocations: int

    validate_selector: bool = False

    def __init__(self, max_tool_invocations: int, validate_selector: bool = False) -> None:
        self.max_tool_invocations = max_tool_invocations
        self.validate_selector = validate_selector

    def validate_label_selector(self, request: ToolCallRequest) -> None:
        if self.validate_selector and "labelSelector" in request.tool_call["args"]:
            label_selector = request.tool_call["args"]["labelSelector"]
            if label_selector is not None:
                # TODO: Add some sanity checks for label selector, e.g. length, pattern, etc.
                if len(label_selector) > 30 or LABEL_SELECTOR_PATTERN.match(label_selector):
                    request.tool_call["args"]["labelSelector"] = ""

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command[Any]]],
    ) -> ToolMessage | Command[Any]:

        self.validate_label_selector(request)
        self.tool_invocations += 1
        if self.tool_invocations > self.max_tool_invocations:
            raise Exception(f"Exceeded maximum tool invocations: {self.max_tool_invocations}")
        try:
            result = await handler(request)
            return result
        except Exception as e:
            raise

class TestAnalystAgent():

    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-4o-mini"])
    @mark.skip(reason="Models seem to no longer exceed the max tool invocations")
    async def test_pod_failure_analysis_to_many_tool_requests(self, kubernetes_mcp_server_ip: str, create_pod_with_faulty_image, model_name: str) -> None:

        ns = "test-failure-analysis-too-many-tool-requests"
        create_pod_with_faulty_image(ns, "faulty-pod")

        client = await self.get_kubernetes_mcp_server(kubernetes_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))

            system_prompt = prompts.POD_ANALYSIS_SYSTEM_PROMPTS[model_name.split(":")[1]]
            max_invocation_middleware = ToolCallValidationMiddleware(max_tool_invocations=5, validate_selector=False)

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

    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-4o-mini"])
    async def test_pod_failure_analysis(self, kubernetes_mcp_server_ip: str, create_pod_with_faulty_image, model_name: str) -> None:

        ns = "test-pod-failure-analysis"
        create_pod_with_faulty_image(ns, "faulty-pod")

        client = await self.get_kubernetes_mcp_server(kubernetes_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))
            self.enhance_pod_list_tools_description(tools)

            system_prompt = prompts.POD_ANALYSIS_SYSTEM_PROMPTS[model_name.split(":")[1]]
            max_invocation_middleware = ToolCallValidationMiddleware(max_tool_invocations=4, validate_selector=True)

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

            response = await agent.agent.ainvoke(prompt)

            analysis: AnalysisResult = response["structured_response"]

            assert analysis.classification == "image_pull_error"
            assert "pod" in analysis.labels
            assert "image" in analysis.labels


    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-6-luna"])
    async def test_deployment_failing_due_to_affinity_analysis(self, kubernetes_mcp_server_ip: str, create_deployment_failing_due_to_affinity, create_model, model_name) -> None:
        ns = "internet-portal"
        create_deployment_failing_due_to_affinity(ns, "webserver")

        client = await self.get_kubernetes_mcp_server(kubernetes_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))
            self.enhance_pod_list_tools_description(tools)

            system_prompt = prompts.POD_ANALYSIS_SYSTEM_PROMPTS[model_name.split(":")[1]]
            max_invocation_middleware = ToolCallValidationMiddleware(max_tool_invocations=6, validate_selector=True)

            agent = await self.create_agent(create_model(model_name), system_prompt, tools, [max_invocation_middleware])
            prompt = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"There is a deployment failing in the namespace {ns}\n"
                            f"Analyze the deployment failure and provide a summary, reason,"
                            f"recommended fix, classification and labels."
                        ),
                    }
                ]
            }

            response = await agent.agent.ainvoke(prompt)

            analysis: AnalysisResult = response["structured_response"]

            assert analysis.classification == "unschedulable"
            assert "deployment" in analysis.labels


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

    def enhance_pod_list_tools_description(self, tools: list[BaseTool]) -> None:
        for tool in tools:
            if tool.name == "pods_list_in_namespace":
                tool.description = (
                    "This tool lists all pods in a given namespace. "
                    "It takes a single argument 'namespace' which is the name of the namespace to list pods from. "
                    "The output is a JSON array of pod names."
                )
                tool.args["labelSelector"] = {
                    'description': "Optional Kubernetes label selector (e.g. 'app=myapp,env=prod' or 'app in (myapp,yourapp)' or '' for all pods), use this option when you want to filter the pods by label.",
                    'pattern': "^([a-zA-Z0-9](?:[\\w.\\-]{0,61}[a-zA-Z0-9])?)=([a-zA-Z0-9](?:[\\w.\\-]{0,61}[a-zA-Z0-9])?)?$",
                    'type': 'string'
                }
