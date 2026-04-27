"""Glean MCP Server (direct mode).

Exposes Glean chat as MCP tools so coding agents (VS Code + Copilot, Claude Code,
Cursor, etc.) can query your organization's knowledge base.

Uses the same Playwright cookie-based approach as the CLI — no separate service needed.
If no valid session exists, the server will automatically open a browser for SSO login.
"""

import argparse
import asyncio
import json
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict
from urllib.parse import quote

from playwright.async_api import async_playwright, BrowserContext
from mcp.server.fastmcp import FastMCP

from glean_cli.core import (
    PROFILE_DIR,
    detect_tenant_url,
    load_config,
    load_saved_cookies,
    save_config,
    save_storage_state,
    stream_chat,
)

# Config set by main() before mcp.run() is called. The lifespan reads these.
_tenant_url: str = ""
_channel: str | None = None
_skip_self_check: bool = False
_self_check_timeout: float = 30.0

# Runtime state populated by the lifespan inside FastMCP's event loop.
_browser: BrowserContext | None = None
_state_path: str = ""
_sessions: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Initialize Playwright + run self-check inside FastMCP's event loop.

    Critical: the browser MUST be launched in the same event loop that
    handles tool calls. If we launch it in an outer loop and then call
    ``mcp.run()`` (which creates its own loop), Playwright's IPC pipes
    are bound to the wrong loop and cross-loop ``await context.cookies()``
    deadlocks silently.

    If no valid session exists (self-check gets 401/403), the server
    automatically opens a visible browser for SSO login, waits for the
    user to complete it, then restarts headless.
    """
    await _init_browser(_tenant_url, channel=_channel)

    if not _skip_self_check:
        ok = await _self_check(timeout_seconds=_self_check_timeout)
        if not ok:
            # Session invalid — attempt interactive SSO login.
            print("[lifespan] no valid session, launching browser for SSO login...",
                  file=sys.stderr, flush=True)
            await _close_browser()
            await _sso_login(_tenant_url, channel=_channel)
            # Re-init headless after login.
            await _init_browser(_tenant_url, channel=_channel)
            ok = await _self_check(timeout_seconds=_self_check_timeout)
            if not ok:
                print("[lifespan] FATAL: self-check still fails after SSO login.",
                      file=sys.stderr, flush=True)
                sys.exit(2)

        # Session is valid — persist tenant URL for next time.
        cfg = load_config()
        if cfg.get("tenant_url") != _tenant_url:
            cfg["tenant_url"] = _tenant_url
            save_config(cfg)

    try:
        yield
    finally:
        await _close_browser()


mcp = FastMCP(
    "Glean",
    instructions=(
        "Glean is a CHAT agent backed by your organization's knowledge graph "
        "(Confluence, Slack, Jira, Google Drive, GitHub, calendars, directory, etc.) — "
        "NOT a keyword search engine. Operate it like a knowledgeable colleague:\n"
        "\n"
        "1. Phrase queries as natural-language QUESTIONS, not keyword bags. "
        "Question form gets specific, cited evidence; keyword form gets generic tutorials.\n"
        "\n"
        "2. For any non-trivial topic, plan MULTI-TURN within one session_id — "
        "one broad probe + 2-3 targeted follow-ups beats fan-out one-shot queries. "
        "Pronouns and prior topic resolve across turns within the same session_id, "
        "so subsequent turns rank/reframe existing context instead of re-searching. "
        "Stopping after the first turn is the most common failure mode.\n"
        "\n"
        "3. Use FIRST-PERSON ('what have I…', 'my team', 'my reports') — SSO already "
        "scopes to the authenticated user. Passing a name like 'Jerry You' is fragile: "
        "if the directory has a different format the query silently returns nothing.\n"
        "\n"
        "4. RESET (glean_reset_session) when switching to an unrelated topic; "
        "otherwise prior context contaminates the new question. Same topic, "
        "different angle = same session_id; different topic = fresh session_id.\n"
        "\n"
        "5. CITE the artifacts Glean returns (Confluence/Slack/Jira/GitHub URLs are "
        "in the response) — those are the source of truth, not Glean's prose. "
        "Quote numbers from them and surface the links to the user.\n"
        "\n"
        "Tools: glean_chat(query, session_id), glean_reset_session(session_id)."
    ),
    lifespan=_lifespan,
)


def _get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "sessionTrackingToken": secrets.token_urlsafe(16)[:16],
            "tabId": secrets.token_urlsafe(16)[:16],
            "firstEngageTsSec": int(time.time()),
            "chatId": None,
            "chatSessionTrackingToken": None,
        }
    return _sessions[session_id]


@mcp.tool()
async def glean_chat(query: str, session_id: str = "mcp") -> str:
    """Chat with Glean — your org's chat agent over Confluence, Slack, Jira, Drive, GitHub, etc.

    Glean is a CHAT agent, not a keyword search engine. Phrase the query as a
    natural-language QUESTION, and for any non-trivial topic plan MULTI-TURN
    within one session_id (one broad probe + 2-3 follow-ups) rather than a
    single giant query — pronouns and prior topic resolve across turns and
    subsequent calls rank/reframe existing context instead of re-searching.
    Use first-person ("what have I…", "my team") so SSO scopes for you.
    Cite the URLs Glean returns; they are the source of truth.

    Args:
        query: A natural-language question. For follow-ups in a multi-turn
            drill, use pronouns ("from those, which…") and reuse session_id.
        session_id: Conversation key. Reuse the same value to drill into a
            topic; pick a new value (or call glean_reset_session) when
            switching to an unrelated topic. Defaults to "mcp".
    """
    global _browser
    if _browser is None:
        return "Error: Playwright browser not initialized. Restart the MCP server."

    print(f"[glean_chat] query={query!r} session_id={session_id!r}", file=sys.stderr, flush=True)
    started = time.time()

    session = _get_session(session_id)
    aggregated: list[str] = []

    async def on_line(line: str):
        elapsed = time.time() - started
        print(f"[glean_chat] stream line received ({elapsed:.1f}s, {len(line)} chars)", file=sys.stderr, flush=True)
        try:
            obj = json.loads(line)
        except Exception:
            return
        msgs = obj.get("messages") if isinstance(obj, dict) else None
        if isinstance(msgs, list):
            for m in msgs:
                frags = m.get("fragments") if isinstance(m, dict) else None
                if isinstance(frags, list):
                    for f in frags:
                        t = f.get("text") if isinstance(f, dict) else None
                        if isinstance(t, str):
                            aggregated.append(t)
                t2 = m.get("text") if isinstance(m, dict) else None
                if isinstance(t2, str):
                    aggregated.append(t2)

    print("[glean_chat] calling stream_chat...", file=sys.stderr, flush=True)
    result = await stream_chat(_browser, _tenant_url, query, on_line, session)
    elapsed = time.time() - started
    ok = isinstance(result, dict) and result.get("ok")
    print(f"[glean_chat] stream_chat returned ok={ok} in {elapsed:.1f}s", file=sys.stderr, flush=True)

    # Persist cookies after successful response
    if ok:
        await save_storage_state(_browser, _state_path)

    if not ok:
        error = (result or {}).get("error", "Unknown error")
        status = (result or {}).get("status", "")
        print(f"[glean_chat] ERROR status={status} error={error}", file=sys.stderr, flush=True)
        return f"Glean error (status {status}): {error}"

    print(f"[glean_chat] OK, returning {len(aggregated)} fragments ({len(''.join(aggregated))} chars)", file=sys.stderr, flush=True)
    return "".join(aggregated)


@mcp.tool()
async def glean_reset_session(session_id: str = "mcp") -> str:
    """Reset a Glean chat session — call when switching to an UNRELATED topic.

    Glean carries chat context across calls that share a session_id, so an
    unrelated new question on the same session inherits prior context and
    can return contaminated results. Call this (or pick a fresh session_id)
    at topic boundaries. Within one topic, keep the session_id stable so
    follow-up turns can drill into prior content.

    Args:
        session_id: Session identifier to reset. Defaults to "mcp".
    """
    if session_id in _sessions:
        del _sessions[session_id]
    return "Session reset. Next query will start a new conversation."


async def _close_browser() -> None:
    """Gracefully close the current browser context, if any."""
    global _browser
    if _browser is not None:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None


async def _init_browser(tenant_url: str, channel: str | None = None):
    """Launch headless Playwright and load saved cookies."""
    global _browser, _tenant_url, _state_path

    _tenant_url = tenant_url
    os.makedirs(PROFILE_DIR, exist_ok=True)
    _state_path = os.path.join(PROFILE_DIR, "storage_state.json")

    pw = await async_playwright().start()
    launch_kwargs: Dict[str, Any] = {
        "headless": True,
        "args": ["--disable-dev-shm-usage"],
    }
    if channel:
        launch_kwargs["channel"] = channel
    _browser = await pw.chromium.launch_persistent_context(PROFILE_DIR, **launch_kwargs)
    await load_saved_cookies(_browser, _state_path)


async def _sso_login(tenant_url: str, channel: str | None = None,
                     timeout_seconds: float = 300.0) -> None:
    """Open a visible browser for Glean SSO and wait for login to complete.

    The browser navigates to the Glean app entry URL which triggers the
    organisation's SSO flow.  We confirm completion by probing the Glean
    chat API — a 200 there is the only authoritative signal that cookies
    are valid, since URL/title heuristics false-positive on the initial
    ``app.glean.com`` shell load (which is titled "Glean" before any
    redirect).

    Timeout defaults to 5 minutes — SSO flows can involve MFA.
    """
    print(f"[sso-login] opening browser for SSO at {tenant_url}...",
          file=sys.stderr, flush=True)

    pw = await async_playwright().start()
    launch_kwargs: Dict[str, Any] = {
        "headless": False,  # visible so user can interact with SSO
        "args": ["--disable-dev-shm-usage"],
    }
    if channel:
        launch_kwargs["channel"] = channel
    ctx = await pw.chromium.launch_persistent_context(PROFILE_DIR, **launch_kwargs)
    state_path = os.path.join(PROFILE_DIR, "storage_state.json")
    await load_saved_cookies(ctx, state_path)

    page = await ctx.new_page()
    login_url = f"https://app.glean.com/?qe={quote(tenant_url, safe='')}"
    await page.goto(login_url, wait_until="domcontentloaded")
    print("[sso-login] SSO browser opened. Complete login in the browser window.",
          file=sys.stderr, flush=True)
    print(f"[sso-login] this window will close automatically once a Glean API "
          f"probe succeeds (up to {timeout_seconds:.0f}s).",
          file=sys.stderr, flush=True)

    started = time.time()
    success = False
    last_heartbeat = 0.0
    probe_interval = 4.0  # seconds between API probes; spaced out to avoid spamming

    async def _noop(_line: str) -> None:
        return

    while (time.time() - started) < timeout_seconds:
        # Persist whatever cookies the visible browser has accumulated so the
        # API probe sees the latest auth state.
        try:
            await save_storage_state(ctx, state_path)
        except Exception:
            pass

        session = {
            "sessionTrackingToken": secrets.token_urlsafe(16)[:16],
            "tabId": secrets.token_urlsafe(16)[:16],
            "firstEngageTsSec": int(time.time()),
            "chatId": None,
            "chatSessionTrackingToken": None,
        }
        try:
            result = await asyncio.wait_for(
                stream_chat(ctx, tenant_url, "ping (mcp sso probe)", _noop, session),
                timeout=15.0,
            )
            if isinstance(result, dict) and result.get("ok"):
                success = True
                break
        except Exception:
            pass

        # Heartbeat every ~15s with the current URL so the user (and logs) can
        # see we're still alive and waiting.
        now = time.time()
        if now - last_heartbeat >= 15.0:
            try:
                current = page.url or ""
            except Exception:
                current = ""
            print(f"[sso-login] still waiting ({int(now - started)}s)… current URL: {current[:160]}",
                  file=sys.stderr, flush=True)
            last_heartbeat = now

        await asyncio.sleep(probe_interval)

    elapsed = time.time() - started
    try:
        await save_storage_state(ctx, state_path)
    except Exception:
        pass

    if success:
        print(f"[sso-login] login confirmed in {elapsed:.1f}s. Closing visible browser.",
              file=sys.stderr, flush=True)
    else:
        print(f"[sso-login] WARNING: timed out after {elapsed:.0f}s waiting for SSO. "
              f"Saving partial session.",
              file=sys.stderr, flush=True)

    try:
        await ctx.close()
    except Exception:
        pass


async def _self_check(timeout_seconds: float = 30.0) -> bool:
    """Send a 'hello' query to Glean to verify the server can reach the tenant.

    Returns True if the check passed, False if auth failed (401/403) and
    the caller should attempt SSO login.  Exits the process on hard
    failures (network, timeout, empty response).
    """
    print(f"[self-check] sending hello to {_tenant_url}...", file=sys.stderr, flush=True)

    session = {
        "sessionTrackingToken": secrets.token_urlsafe(16)[:16],
        "tabId": secrets.token_urlsafe(16)[:16],
        "firstEngageTsSec": int(time.time()),
        "chatId": None,
        "chatSessionTrackingToken": None,
    }

    received: list[str] = []

    async def on_line(line: str) -> None:
        received.append(line)

    from datetime import datetime, timezone

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    hello_msg = f"hello (MCP self-check at {timestamp})"

    started = time.time()
    try:
        result = await asyncio.wait_for(
            stream_chat(_browser, _tenant_url, hello_msg, on_line, session),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        print(
            f"[self-check] FAILED: no response from Glean within {timeout_seconds:g}s. "
            f"Check network connectivity to {_tenant_url}.",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(2)

    elapsed = time.time() - started
    ok = isinstance(result, dict) and result.get("ok")
    if not ok:
        status = (result or {}).get("status", "?")
        error = (result or {}).get("error", "unknown error")
        msg = f"[self-check] FAILED (status {status}, {elapsed:.1f}s): {error}"
        if status in (401, 403):
            msg += "\nSession expired — will attempt SSO login."
            print(msg, file=sys.stderr, flush=True)
            return False
        print(msg, file=sys.stderr, flush=True)
        sys.exit(2)

    if not received:
        print(
            f"[self-check] FAILED: Glean returned 200 but no message body ({elapsed:.1f}s).",
            file=sys.stderr,
            flush=True,
        )
        sys.exit(2)

    # Persist refreshed cookies after a successful round-trip.
    await save_storage_state(_browser, _state_path)
    print(
        f"[self-check] OK: hello round-trip in {elapsed:.1f}s ({len(received)} stream lines).",
        file=sys.stderr,
        flush=True,
    )
    return True


def main():
    ap = argparse.ArgumentParser(description="Glean MCP Server (direct mode)")
    ap.add_argument(
        "--tenant-url",
        default=os.environ.get("GLEAN_TENANT_URL", ""),
        help="Your Glean tenant URL, e.g. https://acme.glean.com (env: GLEAN_TENANT_URL)",
    )
    ap.add_argument(
        "--channel",
        default=os.environ.get("GLEAN_BROWSER_CHANNEL", None),
        help="Browser channel to use (e.g. 'chrome', 'msedge'). Env: GLEAN_BROWSER_CHANNEL",
    )
    ap.add_argument(
        "--skip-self-check",
        action="store_true",
        help="Skip the startup hello round-trip to Glean. Use for offline/debug only.",
    )
    ap.add_argument(
        "--self-check-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for the hello round-trip before failing (default: 30).",
    )
    # Keep --service-url for backward compatibility but ignore it
    ap.add_argument("--service-url", default=None, help=argparse.SUPPRESS)
    args = ap.parse_args()

    tenant_url = args.tenant_url.rstrip("/") if args.tenant_url else ""
    if not tenant_url:
        tenant_url = detect_tenant_url()
        if tenant_url:
            print(f"[config] auto-detected tenant URL: {tenant_url}", file=sys.stderr)
        else:
            print(
                "Error: could not determine tenant URL.\n"
                "Provide --tenant-url, set GLEAN_TENANT_URL, or run once with "
                "the URL so it gets saved for future use.",
                file=sys.stderr,
            )
            sys.exit(1)

    # Stash config for the lifespan to read inside FastMCP's event loop.
    # Browser init and self-check now happen there, not here, so that
    # Playwright's IPC pipes are bound to the same loop that dispatches tools.
    global _tenant_url, _channel, _skip_self_check, _self_check_timeout
    _tenant_url = tenant_url
    _channel = args.channel
    _skip_self_check = args.skip_self_check
    _self_check_timeout = args.self_check_timeout

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
