import os
import sys

# TODO: Examine different approaches on how to apply authentication
# information to git.

def main() -> None:
    prompt = sys.argv[1] if len(sys.argv) > 1 else ""
    if "Username" in prompt:
        if "GIT_USERNAME" not in os.environ:
            print("Error: GIT_USERNAME environment variable is not set.", file=sys.stderr)
            raise SystemExit(1)
        print(os.environ["GIT_USERNAME"])
    elif "Password" in prompt:
        if "GIT_TOKEN" not in os.environ:
            print("Error: GIT_TOKEN environment variable is not set.", file=sys.stderr)
            raise SystemExit(1)
        print(os.environ["GIT_TOKEN"])
    else:
        raise SystemExit(1)