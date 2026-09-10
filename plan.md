# Multi-agent LangChain setup plan (uv monorepo)

## Problem and approach
Need a repository where each agent is independently runnable (own project + own venv), while dependency versions are updated in one place.  
Approach: use a uv workspace with a single root `uv.lock`, plus:
- `agents-common` for shared runtime code used by most agents.
- `agent-tools` as a separate agent project that does **not** depend on `agents-common` but still shares the same workspace lock.

## Repository shape
```text
repo/
  pyproject.toml                 # workspace root
  uv.lock                        # single lock file for all projects
  agents-common/
    pyproject.toml
    src/agents_common/
    tests/
    Dockerfile
  agents/
    agent-a/
      pyproject.toml
      src/agent_a/
      tests/
      Dockerfile
    agent-b/
      pyproject.toml
      src/agent_b/
      tests/
      Dockerfile
    agent-tools/
      pyproject.toml
      src/agent_tools/
      tests/
      Dockerfile
```

## uv workspace concept (what it is and why it matters)
A **uv workspace** groups multiple Python projects (packages/apps) in one repository so uv can resolve them together.

Think of it as:
- **many projects**, each with its own `pyproject.toml` and `.venv`
- **one dependency resolution boundary** for the whole repo
- **one lock file (`uv.lock`)** that records exact resolved versions

What uv workspace gives you:
1. **Consistent versions across all agents**: common libs resolve once, preventing drift.
2. **Centralized upgrades**: update versions in one place, re-lock once.
3. **Local package wiring**: workspace members (like `agents-common`) are resolved as local packages, making shared code reuse straightforward.
4. **Independent execution**: each agent can still be synced/run/tested independently via `--project`.

How it works operationally:
1. Root `pyproject.toml` declares workspace members.
2. `uv lock` computes one dependency graph and writes `uv.lock`.
3. `uv sync --project <member>` creates that member’s venv from the shared lock.
4. `uv run --project <member> ...` executes commands in that member context.

In short: workspace solves the “single place to update dependencies” goal without sacrificing “each agent is independently runnable”.

### Important limitation for your question (different `requests` versions)
With a **single uv workspace lock**, members are resolved together to one compatible set.  
If agent A requires `requests==2.31.*` and agent B requires `requests==2.28.*` (conflicting constraints), the workspace resolution is expected to fail rather than allow both conflicting versions.

So for your question:
- **Inside one uv workspace model:** generally **no** for conflicting versions of the same package.
- **If you need per-agent version divergence:** use **independent uv projects** (separate lock files) and connect shared code via path dependency (`agents-common`) instead of making all agents one workspace.

Practical architecture choices:
1. **Consistency-first:** one workspace + one lock (easy global upgrades, no conflicting versions).
2. **Flexibility-first:** no workspace, one lock per agent (allows different versions, but upgrades are decentralized).

## How an agent uses the global lock file

### 1) Configure a workspace in the root `pyproject.toml`
```toml
[tool.uv.workspace]
members = ["agents-common", "agents/*"]
```

This makes `uv.lock` in the root the version source for all workspace members.

### 2) Add shared deps in `agents-common`
`agents-common/pyproject.toml` holds common runtime dependencies (e.g., langchain/langgraph/pydantic) and shared code under `src/agents_common`.

Clarification:
- **Yes** — if `agents-common` declares `langchain` in its dependencies, an agent that depends on `agents-common` will get `langchain` installed transitively.
- Recommended practice: if `agent-a` imports `langchain` directly in its own code, also declare `langchain` directly in `agent-a` dependencies (not only transitively through `agents-common`).
- If `agent-a` only imports `agents_common.*` wrappers and never imports `langchain` directly, keeping `langchain` only in `agents-common` is fine.

### 3) Add `agents-common` as dependency in each agent
Example `agents/agent-a/pyproject.toml`:
```toml
[project]
name = "agent-a"
version = "0.1.0"
dependencies = [
  "agents-common",
  # agent-specific dependencies only
]
```

`agent-tools` is the exception and should not depend on `agents-common`:
```toml
[project]
name = "agent-tools"
version = "0.1.0"
dependencies = [
  # only tool-specific dependencies here (no "agents-common")
]
```

`agent-tools` still participates in the same workspace and uses the same root `uv.lock`.

### 4) Lock once from repository root
```bash
uv lock
```
or for upgrades:
```bash
uv lock --upgrade
```

### 5) Sync per-agent environment with the same global lock
From repo root:
```bash
uv sync --project agents/agent-a --frozen
uv sync --project agents/agent-b --frozen
```

Each command creates/updates that agent’s own `.venv`, but pins versions from the shared root lock.

### 6) Run agent commands with project targeting
```bash
uv run --project agents/agent-a pytest
uv run --project agents/agent-a python -m agent_a.main
```

## Dependency update workflow
1. Bump shared deps in `agents-common/pyproject.toml` (single place).
2. Bump tool-specific deps in `agents/agent-tools/pyproject.toml` when needed.
3. Run `uv lock --upgrade` at root.
4. Re-sync each project with `uv sync --project <member> --frozen`.

Examples:
```bash
uv sync --project agents/agent-a --frozen
uv sync --project agents/agent-tools --frozen
```

## `.env` strategy (centralized keys + per-agent overrides)
Yes, a centralized `.env` is possible and common for shared API keys.

Recommended layering:
1. `repo/.env.shared` (tracked template only; real secret file not committed)  
   - keys shared across most agents (e.g., `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).
2. `agents/<name>/.env` (not committed)  
   - agent-specific settings, endpoint URLs, feature flags.
3. Load order in each agent: **shared first, then agent-local** so local values override shared defaults.

Practical policy:
- Commit only `.env.example` / `.env.shared.example`.
- Add real `.env*` files to `.gitignore`.
- Keep production secrets in a secret manager or CI/CD secrets, not in repository files.

This keeps configuration DRY while preserving per-agent isolation.

## Centralized tooling (lint/format/type-check) strategy
Yes — keep tooling **configuration centralized**, while running tools per project.

Recommended structure:
```text
repo/
  pyproject.toml          # shared tool config (ruff/pytest/mypy/pylint etc.)
  .ruff.toml              # optional dedicated shared config file
  agents-common/
  agents/
```

How it works:
1. Define shared lint/format/type-check rules once at repo root.
2. Add tool dependencies once (root dev group or dedicated tooling project).
3. Execute tools with per-project targeting so each agent is validated independently.

Examples:
```bash
uv run --project agents/agent-a ruff check src tests
uv run --project agents/agent-tools ruff check src tests
uv run --project agents-common pytest
```

CI pattern:
1. Matrix by member (`agents-common`, `agent-a`, `agent-b`, `agent-tools`).
2. Same shared lint rules for all members.
3. Optionally allow per-member exceptions only when strictly necessary (e.g., legacy constraints), via narrow local override files.

This gives one policy definition with isolated execution per agent.

## Todos
- Define root workspace configuration.
- Create `agents-common` package baseline.
- Create first reusable agent template (`src/tests/Dockerfile/pyproject`).
- Add CI matrix to run tests for `agents-common` and each agent.

## Notes
- Keep `tests` unless you intentionally want `test`; both work, `tests` is the common convention.
- If later needed, `agents-common` can be published as a private package; start with local workspace dependency for simplicity.
- Implement reusable tool implementations in `agents/agent-tools/src/agent_tools`.