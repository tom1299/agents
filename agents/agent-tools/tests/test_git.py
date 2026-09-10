import os

import tempfile
import unittest

from agent_tools.git import clone_repository

class GitTest(unittest.TestCase):

    def test_clone_repository(self) -> None:
        target_folder = tempfile.mkdtemp()
        repo_url = "https://github.com/tom1299/private"
        clone_repository.func(repo_url, target_folder)

        git_folder_path = os.path.join(target_folder, ".git")
        self.assertTrue(os.path.exists(git_folder_path),
                        f"Expected {git_folder_path} to exist after cloning.")

        readme_path = f"{target_folder}/README.md"
        self.assertTrue(os.path.exists(readme_path),
                        f"Expected {readme_path} to exist after cloning the.")
