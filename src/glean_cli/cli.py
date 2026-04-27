import argparse
import asyncio
import json
import secrets
import os
import sys
import time
from datetime import datetime
from urllib.parse import quote

from playwright.async_api import async_playwright
from glean_cli.core import (
    now_iso as core_now_iso,
    detect_tenant_url,
    load_config,
    save_config,
    load_saved_cookies as core_load_saved_cookies,
    save_storage_state as core_save_storage_state,
    print_tenant_cookie_info as core_print_cookie_info,
    stream_chat as core_stream_chat,
)


async def ensure_logged_in(context, page, tenant_url: str) -> None:
    # Navigate to app entry which will handle SSO and tenant routing
    login_url = f"https://app.glean.com/?qe={quote(tenant_url, safe='')}"
    await page.goto(login_url, wait_until="domcontentloaded")
    print("A browser window opened for SSO. Complete login, then return here.")
    print(f"\nIf the browser did not open, copy this URL into any browser:\n  {login_url}\n")
    input("Press Enter after you are fully signed in and can see Glean… ")



def _default_output_path() -> str:
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.abspath(f"glean_chat-{ts}.md")


async def _save_markdown_transcript(tenant_url: str, prompt: str, final_text: str, events, raw_lines, out_path: str | None):
    path = out_path or _default_output_path()
    try:
        dirn = os.path.dirname(path)
        if dirn:
            os.makedirs(dirn, exist_ok=True)
        file_exists = os.path.exists(path)
        mode = "a" if file_exists else "w"
        with open(path, mode, encoding="utf-8") as f:
            if not file_exists:
                f.write(f"# Glean Chat\n\n")
                f.write(f"- Tenant: {tenant_url}\n")
                f.write(f"- Started: {core_now_iso()}\n\n")
            f.write("## Prompt\n\n")
            f.write(prompt + "\n\n")
            f.write("## Response\n\n")
            f.write(final_text + "\n\n")
            # No need to persist progress events or raw stream
    except Exception:
        # Best-effort; ignore file errors to not disrupt CLI
        pass
    else:
        print(f"Saved transcript to: {path}")


def _rand_token(n: int = 16) -> str:
    # URL-safe token; truncate to requested length
    return secrets.token_urlsafe(n)[:n]


async def main_async(tenant_url: str, prompt: str, headless: bool, raw: bool, out_path: str | None, channel: str | None = None) -> int:    # Persist tenant URL for future auto-detection
    cfg = load_config()
    if cfg.get("tenant_url") != tenant_url:
        cfg["tenant_url"] = tenant_url
        save_config(cfg)
    # Use a persistent profile so SSO doesn’t repeat every run
    prof_path = os.path.expanduser("~/.glean_cli/profile")
    os.makedirs(prof_path, exist_ok=True)

    async with async_playwright() as p:
        # Session tokens reused across prompts to keep a single chat session
        session = {
            "sessionTrackingToken": _rand_token(16),
            "tabId": _rand_token(16),
            "firstEngageTsSec": int(time.time()),
            # Will be set after first response lines
            "chatId": None,
            "chatSessionTrackingToken": None,
        }

        printed_cookie_info = False
        while True:
            # Determine the prompt for this turn
            current_prompt = prompt if prompt is not None else input("You: ")
            prompt = None  # subsequent turns ask interactively

            # Phase 1: Try headless first (silent) to avoid popping a window if session is valid.
            phases = [True] if headless else [True, False]
            success = False
            for is_headless in phases:
                launch_kwargs = {
                    "headless": is_headless,
                    "args": ["--disable-dev-shm-usage"],
                }
                if channel:
                    launch_kwargs["channel"] = channel
                browser = await p.chromium.launch_persistent_context(
                    prof_path,
                    **launch_kwargs,
                )
                page = await browser.new_page()
                try:
                    # Load saved cookies (session or otherwise) into context to increase reuse chances
                    state_path = os.path.join(prof_path, "storage_state.json")
                    await core_load_saved_cookies(browser, state_path)
                    # Navigate to app entry
                    try:
                        app_entry = f"https://app.glean.com/?qe={quote(tenant_url, safe='')}"
                        await page.goto(app_entry, wait_until="domcontentloaded")
                    except Exception:
                        pass

                    # First attempt without forcing login; prefer context.request in headless to avoid evaluate issues
                    print("Sending prompt to Glean…")
                    aggregated = []
                    raw_lines = []
                    events = []
                    status = 0
                    if is_headless:
                        # Stream via httpx using auth cookies from the context
                        async def on_line(line: str):
                            raw_lines.append(line)
                            try:
                                obj = json.loads(line)
                            except Exception:
                                return
                            msgs = obj.get("messages") if isinstance(obj, dict) else None
                            if isinstance(msgs, list):
                                for m in msgs:
                                    mt = m.get("messageType") if isinstance(m, dict) else None
                                    sid = m.get("stepId") if isinstance(m, dict) else None
                                    if mt or sid:
                                        print(f"[event] messageType={mt or ''} stepId={sid or ''}")
                                        events.append({"messageType": mt, "stepId": sid})
                                    frags = m.get("fragments") if isinstance(m, dict) else None
                                    if isinstance(frags, list):
                                        for f in frags:
                                            t = f.get("text") if isinstance(f, dict) else None
                                            if isinstance(t, str):
                                                aggregated.append(t)
                                    t2 = m.get("text") if isinstance(m, dict) else None
                                    if isinstance(t2, str):
                                        aggregated.append(t2)

                        result = await core_stream_chat(browser, tenant_url, current_prompt, on_line, session)
                        ok = isinstance(result, dict) and result.get("ok")
                        status = (result or {}).get("status", 0)
                        if ok:
                            if not printed_cookie_info:
                                await core_print_cookie_info(browser, tenant_url)
                                printed_cookie_info = True
                            final_text = "\n".join(raw_lines) if raw else "".join(aggregated)
                            print("\n=== Glean Response ===\n")
                            print(final_text)
                            # Persist latest storage state for next runs
                            await core_save_storage_state(browser, state_path)
                            await _save_markdown_transcript(tenant_url, current_prompt, final_text, events, raw_lines, out_path)
                            success = True
                            # Prompt next turn
                            break
                    else:
                        # Visible mode: also use httpx streaming; window is for SSO only
                        async def on_line(line: str):
                            raw_lines.append(line)
                            try:
                                obj = json.loads(line)
                            except Exception:
                                return
                            msgs = obj.get("messages") if isinstance(obj, dict) else None
                            if isinstance(msgs, list):
                                for m in msgs:
                                    mt = m.get("messageType") if isinstance(m, dict) else None
                                    sid = m.get("stepId") if isinstance(m, dict) else None
                                    if mt or sid:
                                        print(f"[event] messageType={mt or ''} stepId={sid or ''}")
                                        events.append({"messageType": mt, "stepId": sid})
                                    frags = m.get("fragments") if isinstance(m, dict) else None
                                    if isinstance(frags, list):
                                        for f in frags:
                                            t = f.get("text") if isinstance(f, dict) else None
                                            if isinstance(t, str):
                                                aggregated.append(t)
                                    t2 = m.get("text") if isinstance(m, dict) else None
                                    if isinstance(t2, str):
                                        aggregated.append(t2)
                        result = await core_stream_chat(browser, tenant_url, current_prompt, on_line, session)
                        ok = isinstance(result, dict) and result.get("ok")
                        status = (result or {}).get("status", 0)
                        if ok:
                            if not printed_cookie_info:
                                await core_print_cookie_info(browser, tenant_url)
                                printed_cookie_info = True
                            final_text = "\n".join(raw_lines) if raw else "".join(aggregated)
                            print("\n=== Glean Response ===\n")
                            print(final_text)
                            await core_save_storage_state(browser, state_path)
                            await _save_markdown_transcript(tenant_url, current_prompt, final_text, events, raw_lines, out_path)
                            success = True
                            break
                    if status in (401, 403) and is_headless:
                        # Need login; escalate to visible phase
                        await browser.close()
                        print("Not signed in or session expired. Opening SSO login…")
                        continue
                    if status in (401, 403) and (not is_headless):
                        await ensure_logged_in(browser, page, tenant_url)
                        try:
                            app_entry = f"https://app.glean.com/?qe={quote(tenant_url, safe='')}"
                            await page.goto(app_entry, wait_until="domcontentloaded")
                        except Exception:
                            pass
                        if not printed_cookie_info:
                            await core_print_cookie_info(browser, tenant_url)
                            printed_cookie_info = True
                        aggregated.clear()
                        raw_lines.clear()
                        events.clear()
                        result = await core_stream_chat(browser, tenant_url, current_prompt, on_line, session)
                        if isinstance(result, dict) and result.get("ok"):
                            final_text = "\n".join(raw_lines) if raw else "".join(aggregated)
                            print("\n=== Glean Response ===\n")
                            print(final_text)
                            await core_save_storage_state(browser, state_path)
                            await _save_markdown_transcript(tenant_url, current_prompt, final_text, events, raw_lines, out_path)
                            success = True
                            break
                        print("\nRequest failed:", result)
                        break

                    # Other failures
                    print("\nRequest failed:", result)
                    break
                finally:
                    await browser.close()
            # If we succeeded, loop for next prompt; otherwise, stop with error
            if not success:
                return 1


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Glean CLI: SSO login + chat prompt")
    ap.add_argument("--tenant-url", default=os.environ.get("GLEAN_TENANT_URL", ""),
                     help="Your tenant base URL, e.g. https://acme.glean.com (env: GLEAN_TENANT_URL). "
                          "Auto-detected from previous sessions if omitted.")
    ap.add_argument("--prompt", help="Prompt to send to chat. If omitted, you will be asked interactively.")
    ap.add_argument("--headless", action="store_true", help="Run browser headless (requires existing session)")
    ap.add_argument("--channel", help="Browser channel to use instead of bundled Chromium (e.g. 'chrome', 'msedge'). Use this if SSO fails in the default browser.")
    ap.add_argument("--raw", action="store_true", help="Print raw JSON lines from the stream")
    ap.add_argument("-o", "--output", help="Write conversation to a Markdown file. If omitted, a timestamped .md file is created.")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv or sys.argv[1:])
    tenant_url = (args.tenant_url or "").rstrip("/")
    if not tenant_url:
        tenant_url = detect_tenant_url()
        if tenant_url:
            print(f"Auto-detected tenant URL: {tenant_url}")
        else:
            print(
                "Error: could not determine tenant URL.\n"
                "Provide --tenant-url or set GLEAN_TENANT_URL.",
                file=sys.stderr,
            )
            return 1
    prompt = args.prompt or input("Enter your prompt: ")
    return asyncio.run(main_async(tenant_url, prompt, args.headless, args.raw, args.output, channel=args.channel))


if __name__ == "__main__":
    raise SystemExit(main())
