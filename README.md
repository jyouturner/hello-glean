# Hello Glean! The Bridge Between Agent and Glean

Programmatic access to [Glean](https://glean.com) — query your organization's knowledge base from the command line, integrate it into AI agent workflows, or use it as a tool in VS Code with GitHub Copilot.

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

Glean's web and desktop apps are great for humans, but AI agents need programmatic access. This project bridges that gap — it lets your coding assistants and automation scripts tap into the same enterprise knowledge that Glean has already indexed and connected:

- **CLI** — Chat with Glean from your terminal. Ask questions, get answers with source links, save transcripts.
- **MCP Server** — Connect Glean to coding agents like GitHub Copilot, Claude Code, or Cursor. Your AI assistant can look up internal docs, past decisions, and team knowledge while helping you code. Talks directly to Glean — no separate service needed.
- **Agent Skill** — A drop-in skill at `skills/glean-mcp/` that teaches an agent how to use the MCP effectively (multi-turn chat, first-person SSO scoping, natural-language questions vs keyword bags).

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

# Chat with Glean (opens browser for SSO on first run)
uv run python -m glean_cli.cli --tenant-url https://your-tenant.glean.com --prompt "hello Glean?"
```

> **Finding your tenant URL:** Sign in to Glean in your browser. The URL bar will show something like
> `https://app.glean.com/?qe=https%3A%2F%2Fyour-tenant.glean.com` — the part after `qe=` (decoded) is your tenant URL.

On the first run, a browser window opens for SSO login. Complete the sign-in, then the CLI sends your prompt and saves the response to a local Markdown file.

After the first run, your session is saved to `~/.glean_cli/profile/` and the tenant URL is remembered in `~/.glean_cli/config.json` — subsequent runs need neither a browser nor `--tenant-url`:

```bash
# No --tenant-url needed after first run
uv run python -m glean_cli.cli --prompt "what were the Q4 goals?"
```

## How it works

```
You / AI Agent
    |
    v
┌─────────────┐     ┌──────────────────────┐
│  CLI        │     │  MCP Server          │
│  (terminal) │     │  (VS Code / Copilot, │
│             │     │   Claude Code,       │
│             │     │   Cursor)            │
└──────┬──────┘     └──────────┬───────────┘
       │                       │
       │  HTTPS (Playwright cookies)
       v                       v
       ┌──────────────────────────────────┐
       │        Glean Tenant APIs         │
       └──────────────────────────────────┘
```

Both the **CLI** and **MCP Server** talk directly to Glean using Playwright session cookies — no intermediate service or admin-provisioned API token needed.

## Usage

### CLI

```bash
# Interactive multi-turn chat
uv run python -m glean_cli.cli --tenant-url https://your-tenant.glean.com

# Single prompt with transcript
uv run python -m glean_cli.cli --tenant-url https://your-tenant.glean.com \
  --prompt "summarize the Q4 planning doc" \
  -o summary.md
```

Options:
- `--tenant-url` — Your Glean tenant URL. Auto-detected after first run; only needed once.
- `--prompt` — First prompt; if omitted, you'll be asked interactively
- `--headless` / `--no-browser` — Skip opening a browser window (requires existing session)
- `--channel` — Browser channel to use instead of bundled Chromium (e.g. `chrome`, `msedge`). Use this if SSO fails in the default browser.
- `--raw` — Print raw JSON stream instead of aggregated text
- `-o, --output` — Save transcript to a Markdown file

### MCP Server (for VS Code, Copilot, Claude Code, Cursor)

The MCP server lets AI coding agents query Glean as a tool. It talks directly to Glean — no separate service needed.

If you've already used the CLI once (which saves your tenant URL and session), the MCP server needs **zero configuration** — it auto-detects the tenant URL and reuses your session cookies. If the session has expired, it automatically opens a browser for SSO login.

**VS Code / Copilot** — Add to your `.vscode/mcp.json` or global MCP config:

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

> **Note:** `--tenant-url` is optional if you've run the CLI before. To be explicit or override:
> `"--tenant-url", "https://your-tenant.glean.com"`

**Claude Code:**

```bash
claude mcp add glean -- uv run --directory /path/to/hello-glean python -m glean_cli.mcp_server
```

**3. Use it** — ask your AI assistant things like:
- "Use Glean to find our API rate limiting policy"
- "Search Glean for the onboarding checklist"
- "Ask Glean what was decided in last week's architecture review"

Tools exposed: `glean_chat` (chat with Glean) and `glean_reset_session` (start fresh conversation).

**4. Install the agent skill (recommended)** — Glean is a chat agent, not a search engine, and that distinction is non-obvious from the tool name alone. The `skills/glean-mcp/` directory contains an Agent Skill that teaches an LLM agent how to use Glean effectively (multi-turn within a session, first-person SSO scoping, natural-language questions vs keyword bags). Install it:

```bash
# For Claude Code (user scope)
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/glean-mcp" ~/.claude/skills/glean-mcp

# Or copy if you prefer (won't auto-update with this repo)
cp -r skills/glean-mcp ~/.claude/skills/
```

The agent will auto-load the skill whenever it's about to call `glean_chat`. See `skills/glean-mcp/SKILL.md` for the operating manual, plus `skills/glean-mcp/patterns/` (reusable patterns) and `skills/glean-mcp/examples/` (worked workflows).

## Session & Authentication

- Sessions are stored in `~/.glean_cli/profile/` (Playwright persistent context).
- Tenant URL and config are saved in `~/.glean_cli/config.json` — auto-detected on subsequent runs.
- No API keys, tokens, or `.env` files needed — authentication is handled entirely through SSO cookies.
- If your session expires, the MCP server automatically opens a browser for re-login. The CLI does the same.

## Without uv

```bash
pip install -r requirements.txt
python -m playwright install chromium
python -m glean_cli.cli --tenant-url https://your-tenant.glean.com --prompt "..."
```

## Releasing

1. Bump version in `pyproject.toml`
2. Tag and push: `git tag v0.2.0 && git push origin v0.2.0`
3. GitHub Actions builds and attaches artifacts to the release
4. Install from release: `uv pip install https://github.com/one-thd/my-glean/releases/download/v0.2.0/glean_cli-0.2.0-py3-none-any.whl`
