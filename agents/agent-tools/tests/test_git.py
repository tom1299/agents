import os

import tempfile
import unittest
from pathlib import Path

from agent_tools.git import clone_repository, get_file_commit_history, get_commit_details_from_history, \
    create_change_from_commit_detail, Change

TEST_DATA_DIR = (
    Path(__file__).resolve().parent / "test-data" / "kubernetes-website"
)

class GitTest(unittest.TestCase):

    def test_clone_repository(self) -> None:

        target_folder = tempfile.mkdtemp()
        repo_url = "https://github.com/tom1299/private"

        success: bool = clone_repository.func(repo_url, target_folder)
        assert success, f"Expected cloning to succeed, but it failed for {repo_url}."

        git_folder_path = os.path.join(target_folder, ".git")
        self.assertTrue(os.path.exists(git_folder_path),
                        f"Expected {git_folder_path} to exist after cloning.")

        readme_path = f"{target_folder}/README.md"
        self.assertTrue(os.path.exists(readme_path),
                        f"Expected {readme_path} to exist after cloning the.")

    def test_clone_repository_wrong_credentials(self) -> None:
        # TODO: Add capturing stdout and stderr ro verify that no sensitive information is printed
        target_folder = tempfile.mkdtemp()
        repo_url = "https://github.com/tom1299/private"

        original_git_username = os.environ.get("GIT_USERNAME")
        original_git_token = os.environ.get("GIT_TOKEN")

        try:
            os.environ["GIT_USERNAME"] = "wrong_username"
            os.environ["GIT_TOKEN"] = "wrong_token"

            success: bool = clone_repository.func(repo_url, target_folder)
            assert not success, f"Expected cloning to fail with wrong credentials, but it succeeded for {repo_url}."
        finally:
            os.environ["GIT_USERNAME"] = original_git_username
            os.environ["GIT_TOKEN"] = original_git_token

@unittest.skipUnless(
    TEST_DATA_DIR.exists(),
    "Missing test data: tests/test-data/kubernetes-website",
)
class GitFileHistoryTest(unittest.TestCase):

    def test_get_file_commit_history(self) -> None:
        repo_path = TEST_DATA_DIR
        since = "1 year ago"
        file_path = "content/en/docs/concepts/services-networking/service.md"

        commit_history = get_file_commit_history.func(repo_path, since, file_path)

        commit_lines = [line for line in commit_history.splitlines() if line.startswith("commit ")]
        self.assertEqual(len(commit_lines), 10, f"Expected 10 commits in the history, but found {len(commit_lines)}.")

    def test_get_commit_details_from_history(self):
        repo_path = TEST_DATA_DIR
        since = "1 year ago"
        file_path = "content/en/docs/concepts/services-networking/service.md"

        commit_history = get_file_commit_history.func(repo_path, since, file_path)
        commit_details_list = get_commit_details_from_history.func(commit_history)

        self.assertEqual(len(commit_details_list), 10, f"Expected 10 commit details, but found {len(commit_details_list)}.")

    def test_create_change_from_commit_detail(self):
        repo_path = TEST_DATA_DIR
        since = "1 year ago"
        file_path = "content/en/docs/concepts/services-networking/service.md"

        commit_history = get_file_commit_history.func(repo_path, since, file_path)
        commit_details_list = get_commit_details_from_history.func(commit_history)

        for commit_detail in commit_details_list:
            change: Change = create_change_from_commit_detail.func(commit_detail)
            assert change.commit_hash is not None, "Expected commit_hash to be set in Change object."
            assert change.date is not None, "Expected date to be set in Change object."
            assert change.changes is not None, "Expected changes to be set in Change object."
            assert change.commit_message is not None, "Expected commit_message to be set in Change object."

            # Selectively check one commit
            if change.commit_hash == "854aaf863c572486e8998060294c4d858dc74101":
                expected_date_str = "Wed Jan 07 04:12:28 2026 +0000"
                expected_date = change.date.strftime("%a %b %d %H:%M:%S %Y %z")
                self.assertEqual(expected_date, expected_date_str, f"Expected date to be {expected_date_str}, but got {expected_date}.")

                self.assertTrue("Fix ordering of Service and Pod in Port definitions example" in change.commit_message)
