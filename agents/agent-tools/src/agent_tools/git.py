import logging
import os
import subprocess
import sysconfig

from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool("is_git_available", description="Checks if Git is available on the system.")
def is_git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

@tool("clone_repository", description="Clones a Git repository to a specified destination.")
# TODO: Add passing timout and depth parameters to the clone_repository function.
def clone_repository(repo_url: str, destination_path: str) -> bool:
    """Clone a Git repository to a specified destination.
    Creates the destination path if it does not exist.
    If cloning fails for any reason, returns False. Otherwise, returns True.
    """
    if not os.path.exists(destination_path):
        os.makedirs(destination_path)

    scripts_dir = Path(sysconfig.get_path("scripts"))
    askpass_path = str(scripts_dir / "git-askpass-helper")

    env = os.environ.copy()
    env["GIT_ASKPASS"] = askpass_path

    try:
        subprocess.run(["git", "clone", repo_url, destination_path], check=True, env=env, timeout=300)
    except subprocess.CalledProcessError:
        logger.error("Failed to clone repository %s to %s", repo_url, destination_path)
        return False
    except subprocess.TimeoutExpired:
        logger.error("Cloning repository %s to %s timed out", repo_url, destination_path)
        return False

    return True
