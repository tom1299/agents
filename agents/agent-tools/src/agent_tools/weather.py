from langchain_core.tools import tool


@tool("get_weather", description="Gets the current weather for a given location.")
def get_weather(location: str) -> str:
    """Get the current weather for a given location."""
    return f"The current weather in {location} is sunny."