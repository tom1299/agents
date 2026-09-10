from langchain.agents import create_agent

from agent_tools.weather import get_weather

agent = create_agent(
    model="openai:gpt-4o-mini",
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)