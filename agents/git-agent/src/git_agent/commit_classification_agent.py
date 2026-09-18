import langchain

from agent_tools.git import Classification

def create_agent(middleware: list, tools: list, checkpointer=None):
    agent_with_middleware = langchain.agents.create_agent(
        # model="openai:gpt-4o-mini",
        model="openai:gpt-5.5",
        tools=tools,
        checkpointer=checkpointer,
        response_format=Classification,
        middleware=middleware,
        system_prompt="You receive a Change object representing a commit in a git repository."
                      "It contains the commit hash, date, changes (diff), subject, and commit message."
                      "Your task is to classify the commit based on"
                      "the semantic impact on the overall document / file changed and it size"
                      "Return a classification object with the fields size and semantic_impact set."
                      "Also add a brief explanation (10-20 words) for the classification in the reason field."
                      "You receive the path to the git repository as well. Always use it to read the file content before and after the commit"
                      "to determine the size and semantic impact of the change. Use tools get_content_before_commit and get_content_after_commit for that"
                      "Only use these tools once per commit."
    )
    return agent_with_middleware


