from __future__ import annotations

import uuid

import pytest

from pathlib import Path
from typing import NotRequired

from langchain.agents import AgentState
from langchain.agents.middleware import wrap_tool_call, AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain.tools.tool_node import ToolCallRequest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from agent_tools.git import add_changes, ChangeHistory, get_content_after_commit, get_content_before_commit
from git_agent.commit_classification_agent import create_agent

from tests.system_prompts import SYSTEM_PROMPT_WITH_TOOLS, SYSTEM_PROMPT_WITHOUT_TOOLS

# TODO: Think about general test data for all agents
TEST_DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "agent-tools"
    / "tests"
    / "test-data"
    / "kubernetes-website"
)

AVAILABLE_LABELS = ["firewall", "service", "ingress", "network-policy",
                    "endpoint", "load-balancer", "cluster-ip", "node-port",
                    "external-ip", "headless-service", "pod-selector"]

class TrackingState(AgentState):
    tool_invocation_count: NotRequired[int]

# Workaround for disabling parallel tool calls. See https://github.com/langchain-ai/langchain/issues/34010
# TODO: Find a better solution, as this one is invoked on every model call, even if no tools are invoked.
class DisableParallelToolCallsMiddleware(AgentMiddleware):

    def wrap_model_call(self, request, handler):
        request.model_settings["parallel_tool_calls"] = False
        return handler(request)

    async def awrap_model_call(self, request, handler):
        request.model_settings["parallel_tool_calls"] = False
        return await handler(request)

# TODO: Convert wrapper style to middleware style for tool invocation counting and remove
# static MAX_TOOL_CALLS constant.
MAX_TOOL_CALLS = 2

# TODO: This wrapper updates the state with tool call invocations but
# when parallel tool calls are enabled, the state is not updated correctly.
# Examine the issue further.
@wrap_tool_call(state_schema=TrackingState)
def tool_invocation_counter_middleware(request: ToolCallRequest, handler) -> ToolMessage | Command:
    result = handler(request)

    count = request.state.get("tool_invocation_count", 0) + 1
    if count > MAX_TOOL_CALLS:
        raise Exception(f"Exceeded maximum tool invocations: {count} > {MAX_TOOL_CALLS}")

    return Command(
        update={
            # Preserve the tool result in the agent message history.
            "messages": [result],
            "tool_invocation_count": count
        }
    )

@pytest.mark.skipif(
    not TEST_DATA_DIR.exists(),
    reason="Missing test data: tests/test-data/kubernetes-website",
)
class TestCommitClassificationAgent:

    @pytest.mark.parametrize("model_name", ["openai:gpt-4o",
                                            "openai:gpt-5.5", "openai:gpt-4o-mini"])
    def test_classify_commit_with_tool_invocations(self, model_name):
        """
        Test the commit classification agent with tool invocations to get content before and after a commit.
        """

        # Memory checkpointer needed to count tool invocations,
        # see wrapper tool_invocation_counter_middleware above.
        inMemoryCheckPointer = InMemorySaver()
        config = {
            "configurable": {
                "thread_id": str(uuid.uuid4())
            }
        }

        # DisableParallelToolCallsMiddleware is needed to avoid concurrent state updates
        middleware = [DisableParallelToolCallsMiddleware(), tool_invocation_counter_middleware]
        tools = [get_content_before_commit, get_content_after_commit]
        agent = create_agent(model_name, middleware=middleware,
                             tools=tools, system_prompt=SYSTEM_PROMPT_WITH_TOOLS, checkpointer=inMemoryCheckPointer)

        # Create prompt requesting tool invocations
        commit_hash = "90d449e0c3fa65cdcf61dac336121f5586644157"
        file_path = "content/en/docs/concepts/services-networking/service.md"
        prompt = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Call tool get_content_before_commit and get_content_after_commit "
                        f"for commit '{commit_hash}', file "
                        f"'{file_path}' in the "
                        f"repo path at {TEST_DATA_DIR} and classify the changes"
                        f"available labels for classification: {AVAILABLE_LABELS}"
                    ),
                }
            ]
        }

        # 4o-mini enters an endless loop of tool invocations.
        if model_name == "openai:gpt-4o-mini":
            with pytest.raises(Exception) as excinfo:
                agent.invoke(prompt, config=config)
            assert "Exceeded maximum tool invocations" in str(excinfo.value)
        else:
            result = agent.invoke(prompt, config=config)
            classified_change = result["structured_response"]

            # We expect 2 tool invocations: one for get_content_before_commit
            # and one for get_content_after_commit.
            assert result["tool_invocation_count"] == 2,\
                f"Expected 2 tool invocations, but got {result['tool_invocation_count']}"

            # Change should be classified as low impact and small size
            assert classified_change.semantic_impact <= 2,\
                f"Expected semantic impact to be lower than 2, but got {classified_change.semantic_impact}"
            assert classified_change.size <= 2,\
                f"Expected size to be lower than 2, but got {classified_change.size}"

            assert "service" in classified_change.labels, "Expected 'service' label"


    @pytest.mark.parametrize("model_name", ["openai:gpt-4o",
                                            "openai:gpt-5.5", "openai:gpt-4o-mini"])
    def test_classify_commit_without_tools(self, model_name):
        repo_path = TEST_DATA_DIR
        commit_hash = "90d449e0c3fa65cdcf61dac336121f5586644157"
        file_path = "content/en/docs/concepts/services-networking/service.md"

        # Prefetch content change since no tools are available to the agent.
        content_after_commit = get_content_after_commit.func(commit_hash=commit_hash, repo_path=str(repo_path), file_path=file_path)

        # TODO: Find an easier way to get the change details than getting the whole history
        change_history: ChangeHistory = ChangeHistory(repo_path=str(repo_path), file_path=file_path, since="1 year ago", changes=[])
        change_history = add_changes.func(change_history)

        # First commit should be the the same as commit_hash
        change = change_history.changes[0]
        assert change.commit_hash == commit_hash

        prompt = {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "Classify the semantic impact and size of the following change:"
                        "The change details are:\n"
                        f"Commit Message: {change.commit_message}\n"
                        f"========================\n"
                        f"========================\n"
                        f"========================\n"
                        f"Available labels for classification: {AVAILABLE_LABELS}\n"
                        f"========================\n"
                        f"========================\n"
                        f"========================\n"
                        f"Changes done: {change.changes}\n"
                        f"========================\n"
                        f"========================\n"
                        f"========================\n"
                        f"The content of the file after the commit '{commit_hash}' is:\n"
                        f"{content_after_commit}"
                    ),
                }
            ]
        }

        agent = create_agent(model=model_name, middleware=[], tools=[], system_prompt=SYSTEM_PROMPT_WITHOUT_TOOLS)

        result = agent.invoke(prompt)

        classified_change = result["structured_response"]

        # 4o-mini evaluates semantic change significantly higher.
        if model_name == "openai:gpt-4o-mini":
            assert classified_change.semantic_impact >= 4,\
                f"Expected semantic impact to low"
        else:
            assert classified_change.semantic_impact <= 2,\
                f"Expected semantic impact to high"

        assert "service" in classified_change.labels, "Expected 'service' label"
