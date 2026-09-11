import os

import tempfile
import unittest

from agent_tools.git import clone_repository

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
