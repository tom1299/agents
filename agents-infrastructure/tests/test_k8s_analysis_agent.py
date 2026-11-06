from fastmcp import Client
from fastmcp.client import StreamableHttpTransport
from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool
from pytest import mark

from agents_infrastructure.agents.analysis_agent import K8sAnalysisAgent, Classification, Label, AnalysisResult
from agents_infrastructure.utils import read_only


class TestAnalystAgent():

    @mark.asyncio
    @mark.parametrize("model_name", ["openai:gpt-4o-mini"])
    async def test_pod_failure_analysis(self, kubernetes_mcp_server_ip: str, create_pod_with_faulty_image, model_name: str) -> None:

        ns = "test-pod-failure-analysis"
        create_pod_with_faulty_image(ns, "faulty-pod")

        transport = StreamableHttpTransport(
            url=f"http://{kubernetes_mcp_server_ip}/mcp",
            headers={
                "Host": "kubernetes-mcp-server"
            }
        )
        client = Client(transport)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))

            agent: K8sAnalysisAgent = K8sAnalysisAgent()
            agent.tools = tools
            agent.model = model_name
            agent.system_prompt = (f"You are a Kubernetes analysis agent. "
                                   f"You analyze problems and provide insights and "
                                   f"recommendations for resolution of given problems statements. "
                                   f"The provided tools connect you to the Kubernetes cluster "
                                   f"and allow you to gather information about resources."
                                   f"Your response must be in the format of the AnalysisResult model."
                                   f"For labels of your response use"
                                   f"{Label .__args__} and for classification use {Classification.__args__}."
                                   )

            agent.create_analysis_agent()
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
            assert set(analysis.labels) == {"pod", "image"}
