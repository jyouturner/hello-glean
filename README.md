# Hello Glean! The Bridge Between Agent and Glean

Give your AI agents — Claude Code, GitHub Copilot, Cursor — productive chat access to your organization's knowledge in [Glean](https://glean.com). Ships with the MCP server *and* the Skill that teaches agents how Glean actually works (it's a chat agent over your enterprise knowledge graph, not a keyword search box — and that distinction is non-obvious).

**No API keys. No admin setup. Just SSO.**

## Why Glean?

[Glean](https://glean.com) is an enterprise search and knowledge platform that connects to your company's SaaS tools — Google Drive, Slack, JIRA, Confluence, GitHub, email, calendars, and dozens more — and makes all of that knowledge searchable and understandable through AI. You can chat with Glean and even create agents within Glean. **It's one of the best ways to get answers grounded in your organization's actual data, not just general internet knowledge.**

## Why this project instead of the official Glean tools?

Glean offers official tools — a [remote MCP server](https://docs.glean.com/administration/platform/mcp/about), a [local MCP server](https://github.com/gleanwork/mcp-server), and a [CLI](https://github.com/gleanwork/glean-cli). However, **all of them require admin-provisioned credentials**:

| Official tool | Requires |
|---|---|
| Remote MCP server | Admin enables MCP + Glean OAuth Authorization Server |
| Local MCP server (`@gleanwork/local-mcp-server`) | `GLEAN_API_TOKEN` from Glean Admin |
| Glean CLI (`glean auth login`) | OAuth client registration or static client configured by admin |

If your organization hasn't set these up (no API tokens issued, no OAuth client registered, no remote MCP enabled), none of the official tools work. You'll see errors like:

```
Error: authentication failed: no OAuth client available: no registration endpoint
and no static client configured
```

**This project works without any admin action.** It authenticates via browser-based SSO — the same login flow you use when visiting `app.glean.com` — using Playwright to manage session cookies. If you can sign in to Glean in a browser, you can use this tool.

## What is this?

This project exposes Glean to AI agents as a chat tool. Two pieces, designed to be used together:

- **MCP Server** — exposes `glean_chat` and `glean_reset_session` to any MCP-compatible coding agent (Claude Code, GitHub Copilot, Cursor, …). The agent can chat with Glean while helping you work.
- **Agent Skill** (`skills/glean-mcp/`) — the operating manual for the MCP. Without it, agents treat `glean_chat` like a keyword search box and get shallow, generic answers. With it, they multi-turn within a session, use first-person SSO scoping, and cite the artifacts Glean returns. **Install both — the Skill is what makes the MCP useful in practice.**

## Prerequisites

- **A Glean account** — You need access to a Glean tenant through your organization. This project authenticates via your company's SSO, so you must be able to sign in to Glean normally.
- **Python 3.10+**
- **uv** — Install with `curl -LsSf https://astral.sh/uv/install.sh | sh`

## Quickstart

```bash
# Clone and install
git clone git@github.com:one-thd/my-glean.git
cd my-glean
uv sync
uv run python -m playwright install chromium
```

Now wire up your agent and install the skill.

### 1. Add the MCP server to your agent

**Claude Code:**

```bash
claude mcp add glean -- uv run --directory "$(pwd)" python -m glean_cli.mcp_server
```

**VS Code / Copilot** — add to your `.vscode/mcp.json` or global MCP config:

```json
{
  "servers": {
    "hello-glean": {
      "type": "stdio",
      "command": "uv",
      "args": [
        "run",
        "--directory", "/path/to/hello-glean",
        "python", "-m", "glean_cli.mcp_server"
      ]
    }
  }
}
```

The first time the agent calls `glean_chat`, a browser opens for SSO login. After that, your session is cached in `~/.glean_cli/profile/` and reused — no further setup.

> **Finding your tenant URL:** Sign in to Glean in your browser. The URL bar shows something like `https://app.glean.com/?qe=https%3A%2F%2Fyour-tenant.glean.com` — the part after `qe=` (decoded) is your tenant URL. Pass it explicitly with `"--tenant-url", "https://your-tenant.glean.com"` in the args list if auto-detection doesn't pick it up.

### 2. Install the Agent Skill

```bash
# Symlink so the skill stays in sync with this repo
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/glean-mcp" ~/.claude/skills/glean-mcp

# Or copy if you prefer (won't auto-update with this repo)
cp -r skills/glean-mcp ~/.claude/skills/
```

The agent auto-loads the skill whenever it's about to call `glean_chat`. See `skills/glean-mcp/SKILL.md` for the operating manual, plus `skills/glean-mcp/patterns/` (reusable patterns) and `skills/glean-mcp/examples/` (worked workflows).

### 3. Try it

Ask your agent things like:

- "Use Glean to find our API rate limiting policy"
- "Ask Glean what was decided in last week's architecture review"
- "Have Glean summarize my team's activity this past week"

The Skill will steer the agent toward natural-language questions, first-person scoping, and multi-turn drilling — so the answers are grounded and cited rather than vague.

## How it works

```
       AI Agent (Claude Code, Copilot, Cursor, …)
                        │
                        │  loads operating manual
                        ▼
              ┌──────────────────┐
              │   Agent Skill    │  (skills/glean-mcp/)
              └────────┬─────────┘
                       │  shapes calls to
                       ▼
              ┌──────────────────┐
              │   MCP Server     │  (glean_chat, glean_reset_session)
              └────────┬─────────┘
                       │  HTTPS (Playwright cookies)
                       ▼
              ┌──────────────────┐
              │  Glean Tenant    │
              └──────────────────┘
```

The **MCP Server** talks directly to Glean using Playwright session cookies — no intermediate service or admin-provisioned API token needed. The **Skill** is markdown consumed by the agent; it doesn't run code itself but shapes how the agent calls `glean_chat`.

## Session & Authentication

- Sessions are stored in `~/.glean_cli/profile/` (Playwright persistent context).
- Tenant URL and config are saved in `~/.glean_cli/config.json` — auto-detected on subsequent runs.
- No API keys, tokens, or `.env` files needed — authentication is handled entirely through SSO cookies.
- If your session expires, the MCP server automatically opens a browser for re-login.

## Without uv

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m glean_cli.mcp_server --tenant-url https://your-tenant.glean.com
```

## Releasing

1. Bump version in `pyproject.toml`
2. Tag and push: `git tag v0.2.0 && git push origin v0.2.0`
3. GitHub Actions builds and attaches artifacts to the release
4. Install from release: `uv pip install https://github.com/one-thd/my-glean/releases/download/v0.2.0/glean_cli-0.2.0-py3-none-any.whl`
