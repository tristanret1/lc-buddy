"""Thin LeetCode client: public GraphQL for problem data, cookie-auth for
run/submit. Standard library only.

Auth: set env LEETCODE_SESSION + LEETCODE_CSRF, or run `lcb auth` which stores
them in ~/.config/lc_buddy/auth.json (chmod 600). Easiest: `lcb auth --from-browser
chrome` pulls both cookies out of the browser you are logged in with (see
browser_cookies.py); with config `auth_browser` set, a 401/403 from LeetCode
triggers one automatic refresh + retry. Manual fallback: copy LEETCODE_SESSION
and csrftoken from DevTools (Application -> Cookies)."""
from __future__ import annotations

import functools
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from .config import AUTH_FILE, load_config

BASE = "https://leetcode.com"
GRAPHQL = f"{BASE}/graphql"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

QUESTION_QUERY = """
query q($slug: String!) {
  question(titleSlug: $slug) {
    questionId questionFrontendId title titleSlug difficulty content
    exampleTestcases sampleTestCase metaData isPaidOnly
    topicTags { name slug }
    codeSnippets { lang langSlug code }
    hints
  }
}"""

USER_QUERY = "query { userStatus { username isSignedIn } }"


class LeetCodeError(RuntimeError):
    pass


class AuthError(LeetCodeError):
    pass


# ---------- auth ----------

def load_auth() -> Optional[dict]:
    sess, csrf = os.environ.get("LEETCODE_SESSION"), os.environ.get("LEETCODE_CSRF")
    if sess and csrf:
        return {"session": sess, "csrf": csrf}
    if AUTH_FILE.exists():
        try:
            data = json.loads(AUTH_FILE.read_text())
            if data.get("session") and data.get("csrf"):
                return data
        except json.JSONDecodeError:
            pass
    return None


def save_auth(session: str, csrf: str) -> None:
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps({"session": session.strip(), "csrf": csrf.strip()}, indent=2))
    os.chmod(AUTH_FILE, 0o600)


def auth_browser() -> Optional[str]:
    """Browser to pull cookies from on auth failure: env LCB_AUTH_BROWSER or config `auth_browser`."""
    return os.environ.get("LCB_AUTH_BROWSER") or load_config().get("auth_browser") or None


def refresh_auth_from_browser(browser: str, profile: Optional[str] = None) -> dict:
    """Read LEETCODE_SESSION + csrftoken from a local browser profile and persist them."""
    from . import browser_cookies
    try:
        ck = browser_cookies.read_cookies(browser, "leetcode.com", profile,
                                         names={"LEETCODE_SESSION", "csrftoken"})
    except browser_cookies.BrowserCookieError as e:
        raise AuthError(f"could not read cookies from {browser}: {e}") from None
    missing = [n for n in ("LEETCODE_SESSION", "csrftoken") if not ck.get(n)]
    if missing:
        raise AuthError(f"{browser} has leetcode.com cookies but not {', '.join(missing)}; "
                        "log in to leetcode.com in that browser first.")
    save_auth(ck["LEETCODE_SESSION"], ck["csrftoken"])
    return {"session": ck["LEETCODE_SESSION"], "csrf": ck["csrftoken"]}


def _retry_with_browser_auth(fn):
    """On AuthError, pull fresh cookies from the configured browser once and retry.
    Skipped when the caller passed explicit `auth`."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AuthError as first:
            browser = auth_browser()
            if not browser or kwargs.get("auth"):
                raise
            try:
                refresh_auth_from_browser(browser)
            except AuthError as e:
                raise AuthError(f"{first}\n  (auto-refresh from {browser} also failed: {e})") from None
            print(f"auth: refreshed LeetCode cookies from {browser}, retrying…", file=sys.stderr)
            return fn(*args, **kwargs)
    return wrapper


def _headers(auth: Optional[dict], referer: str = BASE + "/") -> dict:
    h = {
        "Content-Type": "application/json",
        "User-Agent": UA,
        "Referer": referer,
        "Origin": BASE,
        "Accept": "application/json",
    }
    if auth:
        h["Cookie"] = f"LEETCODE_SESSION={auth['session']}; csrftoken={auth['csrf']}"
        h["x-csrftoken"] = auth["csrf"]
    return h


def _request(url: str, data: Optional[dict] = None, auth: Optional[dict] = None,
             referer: str = BASE + "/", timeout: int = 30) -> Any:
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=_headers(auth, referer),
                                 method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        if e.code in (401, 403):
            raise AuthError(f"LeetCode rejected the request ({e.code}). Cookies expired? "
                            f"Re-run `lcb auth` (or `lcb auth --from-browser chrome`). Body: {detail}") from None
        raise LeetCodeError(f"HTTP {e.code} from {url}: {detail}") from None
    except urllib.error.URLError as e:
        raise LeetCodeError(f"network error talking to LeetCode: {e.reason}") from None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        raise LeetCodeError(f"non-JSON response from {url}: {raw[:200]!r}")


# ---------- public data ----------

def fetch_question(slug: str) -> dict:
    res = _request(GRAPHQL, {"query": QUESTION_QUERY, "variables": {"slug": slug}})
    q = (res or {}).get("data", {}).get("question")
    if not q:
        raise LeetCodeError(f"no such problem on LeetCode: {slug!r}")
    q["metaData"] = json.loads(q["metaData"]) if q.get("metaData") else {}
    return q


@_retry_with_browser_auth
def whoami(auth: Optional[dict] = None) -> dict:
    auth = auth or load_auth()
    if not auth:
        raise AuthError("no credentials. Run `lcb auth --from-browser chrome` (or --session/--csrf).")
    res = _request(GRAPHQL, {"query": USER_QUERY}, auth=auth)
    status = (res or {}).get("data", {}).get("userStatus") or {}
    if not status.get("isSignedIn"):
        raise AuthError("cookies present but LeetCode says not signed in. Refresh them with `lcb auth`.")
    return status


# ---------- judge ----------

def _poll(check_url: str, auth: dict, referer: str, timeout_s: float = 90) -> dict:
    deadline = time.time() + timeout_s
    delay = 1.0
    while time.time() < deadline:
        res = _request(check_url, auth=auth, referer=referer)
        if res and res.get("state") == "SUCCESS":
            return res
        time.sleep(delay)
        delay = min(delay * 1.4, 4.0)
    raise LeetCodeError("timed out waiting for the LeetCode judge")


@_retry_with_browser_auth
def run_code(slug: str, question_id: str, lang: str, code: str, data_input: str,
             auth: Optional[dict] = None) -> dict:
    """Run against custom input (LeetCode 'Run' button). Returns the check payload:
    code_answer, expected_code_answer, status_msg, run_success, std_output_list..."""
    auth = auth or load_auth()
    if not auth:
        raise AuthError("remote run needs credentials. Run `lcb auth` first.")
    referer = f"{BASE}/problems/{slug}/"
    res = _request(f"{BASE}/problems/{slug}/interpret_solution/",
                   {"lang": lang, "question_id": str(question_id), "typed_code": code,
                    "data_input": data_input}, auth=auth, referer=referer)
    iid = (res or {}).get("interpret_id")
    if not iid:
        raise LeetCodeError(f"unexpected interpret response: {res}")
    return _poll(f"{BASE}/submissions/detail/{iid}/check/", auth, referer)


@_retry_with_browser_auth
def submit_code(slug: str, question_id: str, lang: str, code: str,
                auth: Optional[dict] = None) -> dict:
    """Real submission. Returns check payload: status_msg, status_runtime,
    status_memory, runtime_percentile, memory_percentile, total_correct,
    total_testcases, last_testcase, expected_output, code_output, submission_id."""
    auth = auth or load_auth()
    if not auth:
        raise AuthError("submit needs credentials. Run `lcb auth` first.")
    referer = f"{BASE}/problems/{slug}/"
    res = _request(f"{BASE}/problems/{slug}/submit/",
                   {"lang": lang, "question_id": str(question_id), "typed_code": code},
                   auth=auth, referer=referer)
    sid = (res or {}).get("submission_id")
    if not sid:
        raise LeetCodeError(f"unexpected submit response: {res}")
    out = _poll(f"{BASE}/submissions/detail/{sid}/check/", auth, referer, timeout_s=180)
    out["submission_id"] = sid
    out["submission_url"] = f"{BASE}/submissions/detail/{sid}/"
    return out
