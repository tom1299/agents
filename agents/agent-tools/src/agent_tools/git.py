import os
import subprocess
import sysconfig

from pathlib import Path

from langchain_core.tools import tool

@tool("is_git_available", description="Checks if Git is available on the system.")
def is_git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

@tool("clone_repository", description="Clones a Git repository to a specified destination.")
def clone_repository(repo_url: str, destination_path: str) -> None:

    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    scripts_dir = Path(sysconfig.get_path("scripts"))
    askpass_path = str(scripts_dir / "git-askpass-helper")

    env = os.environ.copy()
    env["GIT_ASKPASS"] = askpass_path
    # env["GIT_TERMINAL_PROMPT"] = "0"

    try:
        subprocess.run(["git", "clone", repo_url, destination_path], check=True, env=env)
    except subprocess.CalledProcessError as e:
        raise Exception(f"Failed to clone repository: {e}")