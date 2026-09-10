# agents
A simple repository for agents and agent tools.

> [!NOTE]
> Most code in this repository is AI-generated


## Common commands

```bash
uv sync
uv run --project agents/sample-agent sample-agent
uv run --project agents/agent-tools agent-tools
uv run --project agents-common python -m unittest discover -s agents-common/tests -t agents-common
```

## Add a new agent

```bash
uv init --app --package --no-readme --no-pin-python --no-workspace agents/<agent-name>
uv add --package <agent-name> agents-common --workspace
uv lock
uv sync --project agents/<agent-name>
```

Use `uv run --project agents/<agent-name> <command>` to run it.
