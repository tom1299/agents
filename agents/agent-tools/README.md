# agent-tools

## TODO
* Change getting git details about file to `git log --follow -p -U20 --since="1 year ago" --format="commit:%H%ndate:%aI%nmessage:%B%nchanges:" -- content/en/docs/concepts/services-networking/service.md`
* Rethink git authentication using [ask pass](./src/agent_tools/git_askpass.py) for [git clone](./src/agent_tools/git.py).

## Next steps:
* Implement agent that creates a change description from the history of the git history including adding labels and classification
* Consider larger changes => Get more relevant context from changes (e.g complete file before and after changes)