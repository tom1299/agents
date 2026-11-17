from langchain.agents.factory import STRUCTURED_OUTPUT_ERROR_TEMPLATE
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool, StructuredTool
from pytest import mark, raises

from agents_infrastructure.agents.analysis_agents import AnalysisResult
from agents_infrastructure.k8s_functions import debug_pod
from agents_infrastructure.utils import read_only
from tests import prompts
from tests.base import BaseTestClass
from tests.middleware import ToolCallValidationMiddleware


class TestAnalystAgent(BaseTestClass):

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

    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-6-luna"])
    async def test_connectivity_issue_analysis(self, kubernetes_mcp_server_ip: str, apply_manifest, create_model, model_name) -> None:
        ns = "webapp"
        apply_manifest("frontend-backend-app.yaml", ns)

        client = await self.get_kubernetes_mcp_server(kubernetes_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))
            debug_pod_tool = StructuredTool.from_function(debug_pod)
            tools.extend([debug_pod_tool])

            system_prompt = prompts.POD_ANALYSIS_SYSTEM_PROMPTS[model_name.split(":")[1]]
            max_invocation_middleware = ToolCallValidationMiddleware(max_tool_invocations=10, validate_selector=True)

            agent = await self.create_agent(create_model(model_name), system_prompt, tools, [max_invocation_middleware])
            prompt = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"Interim connectivity failures have been reported between frontend"
                            f" and backend in the namespace {ns}\n"
                            f"Check if the connectivity issue is still present"
                        ),
                    }
                ]
            }

            response = await agent.agent.ainvoke(prompt)

            analysis: AnalysisResult = response["structured_response"]

            # TODO: Assert that debug_pod has been invoked
            assert analysis.classification == "unknown"
            assert "network" in analysis.labels


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
