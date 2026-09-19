from __future__ import annotations

import json
import pytest

from pathlib import Path
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call
from langchain_core.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_tools.git import add_changes, ChangeHistory, get_content_after_commit, get_content_before_commit
from git_agent.commit_classification_agent import create_agent

# TODO: Think about general test data for all agents
TEST_DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "agent-tools"
    / "tests"
    / "test-data"
    / "kubernetes-website"
)

class TrackingState(AgentState):
    tool_call_count: NotRequired[int]

@wrap_tool_call(state_schema=TrackingState)
def tool_invocation_counter_middleware(request: ToolCallRequest, handler) -> ToolMessage | Command:
    result = handler(request)
    return result
    # count = request.state.get("tool_call_count", 0) + 1
    # return Command(
    #     update={
    #         # Preserve the tool result in the agent message history.
    #         "messages": [result],
    #         "tool_call_count": count
    #     }
    # )

class TestCommitClassificationAgent:

    def test_classify_commit_without_change(self):
        # TODO: Examine why endless loop on tool invocation if get before and after commit
        # when using model openai:gpt-4o-mini
        inMemoryCheckPointer = InMemorySaver()
        config = {
            "configurable": {
                "thread_id": "us-weather"
            }
        }

        middleware = [tool_invocation_counter_middleware]
        tools = [get_content_before_commit, get_content_after_commit]
        agent = create_agent(middleware=middleware, tools=tools, checkpointer=inMemoryCheckPointer)

        # result = agent.invoke(message, config=config)
        result = agent.invoke({"messages": [{"role": "user", "content": "Call tool get_content_before_commit and get_content_after_commit for commit '90d449e0c3fa65cdcf61dac336121f5586644157', file 'content/en/docs/concepts/services-networking/service.md' in the repo path at " + str(TEST_DATA_DIR) + " and analyse the changes"}]}, config=config)

        classified_change = result["structured_response"]
        print(f"Classified change for commit 90d449e0c3fa65cdcf61dac336121f5586644157: {classified_change}, {classified_change.reason}")

    @pytest.mark.skip
    def test_classify_commit(self):
        repo_path = TEST_DATA_DIR
        since = "1 year ago"
        file_path = "content/en/docs/concepts/services-networking/service.md"
        change_history = ChangeHistory(repo_path=str(repo_path), since=since, file_path=file_path, changes=[])
        add_changes.func(change_history)

        inMemoryCheckPointer = InMemorySaver()
        config = {
            "configurable": {
                "thread_id": "us-weather"
            }
        }

        change = change_history.changes[0]
        content_after_commit = get_content_after_commit.func(commit_hash=change.commit_hash, repo_path=str(repo_path), file_path=file_path)
        message = {
            "messages": [
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "change": change.model_dump(mode="json"),
                            "repo_path": str(repo_path)
                        }
                    )
                }
            ]
        }

        # TODO: Examine why endless loop on tool invocation if get before and after commit content is fetched
        middleware = [tool_invocation_counter_middleware]
        tools = [get_content_before_commit, get_content_after_commit]
        agent = create_agent(middleware=middleware, tools=tools, checkpointer=inMemoryCheckPointer)

        # result = agent.invoke(message, config=config)
        result = agent.invoke({"messages": [{"role": "user", "content": "Call tool get_content_before_commit and get_content_after_commit for commit '90d449e0c3fa65cdcf61dac336121f5586644157', file 'content/en/docs/concepts/services-networking/service.md' in the repo path at " + str(repo_path) + " and analyse the changes"}]}, config=config)

        classified_change = result["structured_response"]
        print(f"Classified change for commit {change.commit_hash}: {classified_change}, {classified_change.reason}")