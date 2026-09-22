import langchain

from agent_tools.git import Classification

def create_agent(model: str, middleware: list, tools: list, system_prompt=None, checkpointer=None):
    agent_with_middleware = langchain.agents.create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        response_format=Classification,
        middleware=middleware,
        system_prompt=system_prompt
    )
    return agent_with_middleware


