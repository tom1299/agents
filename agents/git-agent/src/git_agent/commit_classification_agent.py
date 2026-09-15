from langchain.agents import create_agent

from agent_tools.git import get_file_commit_history

# TODO: Add the following:
# 1. Clone repo to path if it does not exist
# 2. Get commit history for a specified file path
# 3. For each commit invoke the agent to classify the commit
# 4. Return the classification results

agent = create_agent(
    model="openai:gpt-4o-mini",
    tools=[get_file_commit_history],
    system_prompt="Your task is to analyze the changes in a git commit and classify them based on"
                  "their semantic impact on the overall document / file changed"
)

