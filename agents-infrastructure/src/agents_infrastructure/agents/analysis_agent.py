from typing import Literal

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langgraph.graph.state import CompiledStateGraph

from pydantic import BaseModel, Field

Classification = Literal["image_pull_error", "crash_loop", "oom_killed", "unknown"]
Label = Literal["pod", "image", "network", "resources"]

class AnalysisResult(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    recommend_fix: str = Field(min_length=1, max_length=500)
    classification: Classification
    labels: set[Label]

class K8sAnalysisAgent:

    agent: CompiledStateGraph

    tools: list

    middleware: list[AgentMiddleware]

    system_prompt: str

    model: str

    def __init__(self):
        pass

    def create_analysis_agent(self):
        self.agent = create_agent(
            model=self.model,
            tools=self.tools,
            response_format=AnalysisResult,
            system_prompt=self.system_prompt,
            middleware=self.middleware
        )
