import logging
import os
import re
import subprocess
import sysconfig

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class Change(BaseModel):
    commit_hash: str
    date: datetime
    changes: str
    subject: str
    commit_message: str
    size: int = Field(ge=0, le=10)
    semantic_impact: int = Field(ge=0, le=10)

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
    """Return `git log --no-color --follow -p -U20 --since="1 year ago" --format=commit:%H%n%at%n%s%n%b"` output for a file in a local repository."""
    result = subprocess.run(
        ["git", "log", "--ignore-blank-lines", "--ignore-all-space", "--ignore-space-change",
            "--stat", "--no-color", "--follow", "-p", f"--since={since}",
            "--format=commit:%H%n%at%n%s%n%b",
            "--", file_path],
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
    """
    commits = re.findall(
        r"(?ms)^commit:[0-9a-f]+\n.*?(?=^commit:[0-9a-f]+\n|\Z)",
        commit_history,
    )
    return [commit.strip() for commit in commits if commit.strip()]

@tool(
    "create_change_from_commit_detail",
    description="Creates a Change object from a single commit detail string. See function `get_commit_details_from_history` for how to get the commit details. Size and semantic_impact are not calculated.",
)
def create_change_from_commit_detail(commit_detail: str) -> Change:
    """Create a Change object from a single commit detail string."""

    lines = commit_detail.splitlines()
    commit_hash: str = re.match(r"^commit:([0-9a-f]+)$", lines[0]).group(1)
    date: datetime = datetime.fromtimestamp(int(lines[1]), tz=timezone.utc)
    subject: str = lines[2]
    changes: str = None
    commit_message: str = ""

    for i in range(3, len(lines)):
        if lines[i].startswith("---"):
            changes = "\n".join(lines[i+1:])
            break
        commit_message += lines[i] + "\n"

    if not (commit_hash and date and subject and changes and commit_message):
        raise ValueError("Invalid commit detail format")

    # For simplicity, we can set size and semantic_impact to 0 for now.
    return Change(commit_hash=commit_hash, date=date, subject=subject, changes=changes, commit_message=commit_message, size=0, semantic_impact=0)

def get_content_before_and_after_commit(repo_path: str, file_path: str, commit_hash: str) -> tuple[str, str]:
    # TODO: Verify code
    # Compare with:
    # git show 90d449e0c3fa65cdcf61dac336121f5586644157^:content/en/docs/concepts/services-networking/service.md
    """Get the content of a file before and after a specific commit."""
    # Get the content of the file before the commit
    result_before = subprocess.run(
        ["git", "show", f"{commit_hash}~1:{file_path}"],
        check=True,
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    content_before = result_before.stdout

    # Get the content of the file after the commit
    result_after = subprocess.run(
        ["git", "show", f"{commit_hash}:{file_path}"],
        check=True,
        cwd=repo_path,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    content_after = result_after.stdout

    return content_before, content_after