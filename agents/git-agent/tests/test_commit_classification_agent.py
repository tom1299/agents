import json
import unittest

from pathlib import Path

from agent_tools.git import add_changes, ChangeHistory
from git_agent.commit_classification_agent import agent

# TODO: Think about general test data for all agents
TEST_DATA_DIR = (
    Path(__file__).resolve().parents[2]
    / "agent-tools"
    / "tests"
    / "test-data"
    / "kubernetes-website"
)

class TestCommitClassificationAgent(unittest.TestCase):

    def test_classify_commit(self):
        repo_path = TEST_DATA_DIR
        since = "1 year ago"
        file_path = "content/en/docs/concepts/services-networking/service.md"
        change_history = ChangeHistory(repo_path=str(repo_path), since=since, file_path=file_path, changes=[])
        add_changes.func(change_history)

        for i in range(1):
            change = change_history.changes[i]
            message = {
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "change": change.model_dump(mode="json"),
                                "repo_path": str(repo_path),
                            }
                        )
                    }
                ]
            }

            # TODO: Examine why endless loop on tool invocation if get before and after commit content is fetched

            # result = agent.invoke(message)
            # classified_change = result["structured_response"]
            # print(f"Classified change for commit {change.commit_hash}: {classified_change}, {classified_change.reasoning}")