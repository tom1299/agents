import re
from typing import Callable, Awaitable, Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

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
