from langchain.mcp import MCPAdapter
from langchain_core.tools import BaseTool
from pytest import mark

from agents_infrastructure.agents.analysis_agents import AnalysisResult
from agents_infrastructure.utils import read_only
from tests import prompts
from tests.base import BaseTestClass
from tests.middleware import ToolCallValidationMiddleware


class TestFluxOperatorAnalysisAgent(BaseTestClass):

    @mark.asyncio(loop_scope="session")
    @mark.parametrize("model_name", ["openai:gpt-6-luna"])
    async def test_flux_operator_analysis_agent(self, create_flux_instance, flux_operator_mcp_server_ip, create_model, model_name: str) -> None:
        create_flux_instance("flux-instance.yaml")

        client = await self.get_flux_operator_mcp_server(flux_operator_mcp_server_ip)

        async with MCPAdapter(client) as adapter:
            all_tools = await adapter.list_tools()
            tools: list[BaseTool] = list(filter(read_only, all_tools))

            system_prompt = prompts.FLUX_OPERATOR_ANALYSIS_SYSTEM_PROMPTS[model_name.split(":")[1]]
            max_invocation_middleware = ToolCallValidationMiddleware(max_tool_invocations=10, validate_selector=False)

            agent = await self.create_agent(create_model(model_name), system_prompt, tools, [max_invocation_middleware])
            prompt = {
                "messages": [
                    {
                        "role": "user",
                        "content": (
                            f"A flux instance in the namespace flux-system does not create any resources\n"
                            f"Analyze why no resources are created and provide a summary, reason,"
                            f"recommended fix, classification and labels."
                        )
                    }
                ]
            }

            response = await agent.agent.ainvoke(prompt)

            analysis: AnalysisResult = response["structured_response"]

            assert analysis.classification == "flux_operator"
            assert "configuration" in analysis.labels
