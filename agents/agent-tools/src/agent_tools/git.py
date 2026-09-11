import logging
import os
import re
import subprocess
import sysconfig

from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

@tool("is_git_available",
    description="Checks if Git is available on the system."
)
def is_git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

@tool("clone_repository",
      description="Clones a Git repository to a specified destination."
)
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


@tool(
    "get_file_commit_history",
    description="Returns git log output with patches for a file in a local repository.",
)
def get_file_commit_history(repo_path: str, since: str, file_path: str) -> str:
    """Return `git log --follow -p` output for a file in a local repository."""
    result = subprocess.run(
        ["git", "log", "--follow", "-p", f"--since={since}", "--", file_path],
        check=True,
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout

@tool(
    "get_commit_details_from_history",
    description="Extracts individual commit details from the git log output for a file in a local repository.",
    # TODO: Check whether agents will use description or docstring for the tool.
)
def get_commit_details_from_history(commit_history: str) -> list[str]:
    """
    Extracts individual commit details from the git log output for a file in a local repository.
    See function `get_file_commit_history` for how to get the commit history.

    Output is a list of strings, each string containing the details of a single commit.
    Example of a single commit detail string:

    commit 7aad1e45e9a63de8009022bdc79201f8ef0a2a93
    Author: Kotaro Inoue <k.musaino@gmail.com>
    Date:   Sun Sep 21 21:05:57 2025 +0900

        Use feature_gate_name for embedding feature state

        Co-authored-by: Dipesh Rawat <rawat.dipesh@gmail.com>

    diff --git a/content/en/docs/concepts/services-networking/service.md b/content/en/docs/concepts/services-networking/service.md
    index eb49b1b91d..d9e3d1670f 100644
    --- a/content/en/docs/concepts/services-networking/service.md
    +++ b/content/en/docs/concepts/services-networking/service.md
    @@ -132,7 +132,7 @@ field.

     ### Relaxed naming requirements for Service objects

    -{{< feature-state for_k8s_version="v1.34" state="alpha" >}}
    +{{< feature-state feature_gate_name="RelaxedServiceNameValidation" >}}

     The `RelaxedServiceNameValidation` feature gate allows Service object names to start with a digit. When this feature gate is enabled, Service object names must be valid [RFC 1123 label names](/docs/concepts/overview/working-with-objects/names/#dns-label-names).

    """
    commits_details = re.split(r"(?m)^commit [0-9a-f]+\n", commit_history)
    return [commit_detail.strip() for commit_detail in commits_details if commit_detail.strip()]
