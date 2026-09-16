from langchain.agents import create_agent

from agent_tools.git import get_content_before_commit, get_content_after_commit, Classification

agent = create_agent(
    model="openai:gpt-4o-mini",
    tools=[get_content_before_commit, get_content_after_commit],
    response_format=Classification,
    system_prompt="You receive a Change object representing a commit in a git repository."
                  "Your task is to classify the commit based on"
                  "the semantic impact on the overall document / file changed and it size"
                  "Return a classification object with the fields size and semantic_impact set."
                  "Also add a brief explanation of your reasoning in the reasoning field."
                  "You receive the path to the git repository as well. If necessary use it to read the file content before and after the commit"
                  "to determine the size and semantic impact of the change. Use tools get_content_before_commit and get_content_after_commit for that"
                  "Only use these tools once per commit, and only if you need to read the file content before and after the commit to determine the size and semantic impact of the change."

)

