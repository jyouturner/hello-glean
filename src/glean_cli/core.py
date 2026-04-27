import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Any, Tuple, List
from urllib.parse import urlparse

import httpx

# ── Paths ──────────────────────────────────────────────────────────────
GLEAN_CLI_DIR = os.path.expanduser("~/.glean_cli")
PROFILE_DIR = os.path.join(GLEAN_CLI_DIR, "profile")
CONFIG_PATH = os.path.join(GLEAN_CLI_DIR, "config.json")
STATE_PATH = os.path.join(PROFILE_DIR, "storage_state.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


# ── Config persistence ─────────────────────────────────────────────────

def load_config() -> Dict[str, Any]:
    """Load ``~/.glean_cli/config.json``, returning {} on any failure."""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: Dict[str, Any]) -> None:
    """Persist *cfg* to ``~/.glean_cli/config.json``."""
    os.makedirs(GLEAN_CLI_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def detect_tenant_url() -> str:
    """Try to discover the Glean tenant URL without user input.

    Priority:
      1. ``~/.glean_cli/config.json`` → ``tenant_url``
      2. ``~/.glean_cli/profile/storage_state.json`` → first ``*.glean.com``
         cookie domain that isn't ``app.glean.com``.

    Returns the URL (``https://<tenant>.glean.com``) or empty string.
    """
    # 1. Saved config
    cfg = load_config()
    url = cfg.get("tenant_url", "")
    if url:
        return url.rstrip("/")

    # 2. Cookie domains in the Playwright storage state
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        domains = set()
        for c in state.get("cookies", []):
            dom = (c.get("domain") or "").lstrip(".")
            if re.fullmatch(r"[a-z0-9._-]+\.glean\.com", dom) and dom != "app.glean.com":
                domains.add(dom)
        if len(domains) == 1:
            return f"https://{domains.pop()}"
    except Exception:
        pass

    return ""


def timezone_offset_minutes() -> int:
    if time.localtime().tm_isdst and time.daylight:
        offset = time.altzone
    else:
        offset = time.timezone
    return int(offset / 60)


async def cookie_header_for_host(context, host: str) -> str:
    try:
        cookies = await context.cookies()
    except Exception:
        return ""
    parts = []
    for c in cookies or []:
        dom = (c.get("domain") or "").lstrip(".")
        if not dom:
            continue
        if host == dom or host.endswith("." + dom):
            name = c.get("name")
            val = c.get("value")
            if name is not None and val is not None:
                parts.append(f"{name}={val}")
    return "; ".join(parts)


async def load_saved_cookies(context, state_path: str):
    try:
        if os.path.exists(state_path):
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            cookies = state.get("cookies") or []
            if cookies:
                plw_cookies = []
                for c in cookies:
                    name = c.get("name")
                    value = c.get("value")
                    domain = c.get("domain")
                    path = c.get("path", "/")
                    if not (name and value and (domain or c.get("url"))):
                        continue
                    pc = {"name": name, "value": value, "path": path}
                    if domain:
                        pc["domain"] = domain
                    if c.get("url"):
                        pc["url"] = c["url"]
                    if c.get("expires") is not None:
                        pc["expires"] = c["expires"]
                    if c.get("httpOnly") is not None:
                        pc["httpOnly"] = c["httpOnly"]
                    if c.get("secure") is not None:
                        pc["secure"] = c["secure"]
                    if c.get("sameSite") is not None:
                        pc["sameSite"] = c["sameSite"]
                    plw_cookies.append(pc)
                if plw_cookies:
                    await context.add_cookies(plw_cookies)
    except Exception:
        pass


async def save_storage_state(context, state_path: str):
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        await context.storage_state(path=state_path)
    except Exception:
        pass


async def tenant_cookies(context, tenant_url: str) -> Tuple[str, List[Dict[str, Any]]]:
    host = urlparse(tenant_url).hostname or ""
    try:
        cookies = await context.cookies()
    except Exception:
        return host, []
    rows = []
    now = int(time.time())
    for c in cookies or []:
        dom = (c.get("domain") or "").lstrip(".")
        if not dom:
            continue
        if host == dom or host.endswith("." + dom):
            exp = c.get("expires")
            if isinstance(exp, float):
                exp = int(exp)
            remaining = None
            if isinstance(exp, int) and exp > 0:
                remaining = exp - now
            rows.append({
                "name": c.get("name"),
                "domain": dom,
                "expires": exp,
                "remaining": remaining,
            })
    return host, rows


def fmt_remaining(seconds) -> str:
    if seconds is None:
        return "session"
    try:
        seconds = int(seconds)
    except Exception:
        return "session"
    if seconds <= 0:
        return "expired"
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m and not d:
        parts.append(f"{m}m")
    if not parts:
        parts.append("<1m")
    return " ".join(parts)


async def print_tenant_cookie_info(context, tenant_url: str):
    host, rows = await tenant_cookies(context, tenant_url)
    print(f"\nSession cookies for {host}:")
    if not rows:
        print("- none found")
        return
    for r in rows:
        exp = r.get("expires")
        when = "session" if not isinstance(exp, int) or exp <= 0 else time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(exp))
        print(f"- {r.get('name')}  domain={r.get('domain')}  expires={when}  remaining={fmt_remaining(r.get('remaining'))}")


async def stream_chat(context, tenant_url: str, prompt: str, on_line: Callable[[str], Any], session: Dict[str, Any]):
    tz_offset = timezone_offset_minutes()
    now = now_iso()
    url = f"{tenant_url.rstrip('/')}/api/v1/chat?timezoneOffset={tz_offset}&locale=en"
    base_agent = {
        "agent": "DEFAULT",
        "mode": "DEFAULT",
        "useCanvas": False,
        "useDeepReasoning": False,
        "useDeepResearch": False,
        "clientCapabilities": {"canRenderImages": True},
    }
    body = {
        "agentConfig": base_agent,
        "background": True,
        "clientTools": [],
        "messages": [
            {
                "agentConfig": base_agent,
                "author": "USER",
                "fragments": [{"text": prompt}],
                "messageType": "CONTENT",
                "ts": now,
                "uploadedFileIds": [],
            }
        ],
        "saveChat": True,
        "sourceInfo": {
            "feature": "CHAT",
            "initiator": "USER",
            "platform": "WEB",
            "hasCopyPaste": False,
            "isDebug": False,
        },
        "stream": True,
        "sc": "",
        "sessionInfo": {
            "lastSeen": now,
            "sessionTrackingToken": session.get("sessionTrackingToken") or "tok",
            "tabId": session.get("tabId") or "tab",
            "clickedInJsSession": True,
            "firstEngageTsSec": session.get("firstEngageTsSec", int(time.time())),
            "lastQuery": prompt,
        },
    }
    if session.get("chatId"):
        body["chatId"] = session["chatId"]
    if session.get("chatSessionTrackingToken"):
        body["chatSessionTrackingToken"] = session["chatSessionTrackingToken"]

    host = urlparse(url).hostname or ""
    cookie_hdr = await cookie_header_for_host(context, host)
    headers = {
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "text/plain",
        "origin": "https://app.glean.com",
        "pragma": "no-cache",
        "referer": "https://app.glean.com/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    }
    if cookie_hdr:
        headers["cookie"] = cookie_hdr

    async with httpx.AsyncClient(timeout=None, http2=False) as client:
        try:
            async with client.stream("POST", url, headers=headers, content=json.dumps(body)) as resp:
                if resp.status_code in (401, 403):
                    text = await resp.aread()
                    return {"ok": False, "status": resp.status_code, "error": text.decode(errors="ignore")}
                if not resp.is_success:
                    text = await resp.aread()
                    return {"ok": False, "status": resp.status_code, "error": text.decode(errors="ignore")}
                async for line in resp.aiter_lines():
                    line = (line or "").strip()
                    if not line:
                        continue
                    try:
                        try:
                            obj = json.loads(line)
                            if isinstance(obj, dict):
                                if obj.get("chatId") and not session.get("chatId"):
                                    session["chatId"] = obj.get("chatId")
                                if obj.get("chatSessionTrackingToken") and not session.get("chatSessionTrackingToken"):
                                    session["chatSessionTrackingToken"] = obj.get("chatSessionTrackingToken")
                        except Exception:
                            pass
                        await on_line(line)
                    except Exception:
                        pass
        except httpx.HTTPError as e:
            return {"ok": False, "status": 0, "error": f"httpx error: {e}"}
    return {"ok": True, "status": 200}
