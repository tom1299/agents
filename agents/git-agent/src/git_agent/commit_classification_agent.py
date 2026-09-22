import langchain

from agent_tools.git import Classification

def create_agent(model: str, middleware: list, tools: list, checkpointer=None):
    agent_with_middleware = langchain.agents.create_agent(
        model=model,
        tools=tools,
        checkpointer=checkpointer,
        response_format=Classification,
        middleware=middleware,
        system_prompt="You are a tasked to classify the semantic impact and size of a commit change "
                      "to a file. You have access to tools that can retrieve the content "
                      "of a file before and after a specific commit. Use these tools to"
                      "get the content and analyze the changes and provide a classification." 
                      "Classify the commit change based on the following criteria:"
                      "1. Semantic Impact: Rate the semantic impact of the change on a scale from 0 to 10, "
                      "where 0 indicates no semantic impact and 10 indicates a significant semantic impact."
                      "2. Size: Rate the size of the change on a scale from 0 to 10, "
                      "where 0 indicates a small change and 10 indicates a large change."
                      "3. Reason: Provide a brief explanation for your classification,"
                      "highlighting the key factors that influenced your assessment."
    )
    return agent_with_middleware


