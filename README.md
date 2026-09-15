# vikunja-mcp

Minimal [Model Context Protocol](https://modelcontextprotocol.io) server for a self-hosted
[Vikunja](https://vikunja.io). It lets Claude Code (or any MCP client) read a project's tasks,
create and close them and leave comments, so an agent can work through a board on its own.

Python, stdio transport, two dependencies (`mcp`, `httpx`). No install step: `uvx` runs it
straight from this repository.

## Tools

| Tool | What it does |
| --- | --- |
| `list_projects()` | Projects with id, title and archived flag. |
| `list_tasks(project?, include_done=false)` | Tasks of a project (id or title). Pending only unless `include_done`. |
| `get_task(task_id)` | One task with its full description as plain text. |
| `create_task(title, description?, project?)` | New task; plain-text description, blank line between paragraphs. |
| `update_task(task_id, done?, title?, description?)` | Close (`done=true`), reopen or edit. |
| `add_comment(task_id, text)` | Comment on a task (e.g. the commit that closed it). |
| `list_comments(task_id)` | Comments in order. |

`project` may be omitted wherever `VIKUNJA_PROJECT` is set.

## Per-repo setup (Claude Code)

One command in the repo root writes (or completes) its `.mcp.json`:

```bash
uvx --from git+https://github.com/zurdi15/vikunja-mcp vikunja-mcp-init "My project" --url https://vikunja.example.net
```

`--url` can be omitted when `VIKUNJA_URL` is in the environment; the project defaults to the
folder name. Commit the file. The URL and the default project are plain values; the token is
**not** in the file — it is read from the environment of whoever runs the agent:

```json
{
  "mcpServers": {
    "vikunja": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/zurdi15/vikunja-mcp", "vikunja-mcp"],
      "env": {
        "VIKUNJA_URL": "https://vikunja.example.net",
        "VIKUNJA_PROJECT": "My project",
        "VIKUNJA_TOKEN": "${VIKUNJA_TOKEN}"
      }
    }
  }
}
```

Claude Code expands `${VAR}` in `.mcp.json` from the environment, so each machine only needs
[uv](https://docs.astral.sh/uv/) and the variable:

```bash
# Linux / macOS: in ~/.bashrc, ~/.zshrc or a file you source
export VIKUNJA_TOKEN=tk_…

# Windows (PowerShell, user scope, persistent)
[Environment]::SetEnvironmentVariable('VIKUNJA_TOKEN', 'tk_…', 'User')
```

The token is an API token created in Vikunja (Settings → API tokens) with read/write access
to tasks and comments. Rotate it there and update the variable; nothing else changes.

The first time Claude Code opens a repo with a `.mcp.json` it asks whether to trust the
project's MCP servers. Pin a revision with `git+https://github.com/zurdi15/vikunja-mcp@v0.1.0`
if you want builds to be reproducible.

## Environment

| Variable | Required | Meaning |
| --- | --- | --- |
| `VIKUNJA_URL` | yes | Base URL of the instance, without `/api/v1`. |
| `VIKUNJA_TOKEN` | yes | API token. Never written to disk by this server, never logged. |
| `VIKUNJA_PROJECT` | no | Default project (id or title) for tools with an optional `project`. |

## Local development

```bash
uv run vikunja-mcp                    # starts the stdio server (waits for a client)
uv run --with mcp python scripts/smoke.py   # spawns it and calls list_projects/list_tasks
```

## License

MIT
