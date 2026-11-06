"""Read leetcode.com cookies straight out of a local Chromium-family browser
(Chrome / Arc / Brave / Edge / Chromium) so `lcb auth` never needs a manual
copy-paste from DevTools. Standard library + the system `security` and
`openssl` binaries only.

How Chromium stores cookies on macOS: an sqlite DB per profile; each value is
AES-128-CBC encrypted ("v10" prefix) with a key derived by PBKDF2-SHA1 from a
per-browser password kept in the login keychain ("Chrome Safe Storage").
Chrome ≥ 130 additionally prefixes the plaintext with sha256(host_key).
On Linux the password is the fixed string "peanuts" (1 iteration)."""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

HOME = Path.home()
APP_SUPPORT = HOME / "Library" / "Application Support"
XDG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))

# name -> (user-data dir on macOS, user-data dir on Linux, keychain service name)
BROWSERS: dict[str, tuple[Path, Path, str]] = {
    "chrome":   (APP_SUPPORT / "Google" / "Chrome",             XDG / "google-chrome",  "Chrome Safe Storage"),
    "chromium": (APP_SUPPORT / "Chromium",                      XDG / "chromium",       "Chromium Safe Storage"),
    "arc":      (APP_SUPPORT / "Arc" / "User Data",             XDG / "arc",            "Arc Safe Storage"),
    "brave":    (APP_SUPPORT / "BraveSoftware" / "Brave-Browser", XDG / "BraveSoftware" / "Brave-Browser", "Brave Safe Storage"),
    "edge":     (APP_SUPPORT / "Microsoft Edge",                XDG / "microsoft-edge", "Microsoft Edge Safe Storage"),
}

SALT = b"saltysalt"
IV = b" " * 16


class BrowserCookieError(RuntimeError):
    pass


def _user_data_dir(browser: str) -> Path:
    try:
        mac, linux, _ = BROWSERS[browser]
    except KeyError:
        raise BrowserCookieError(f"unknown browser {browser!r}; choose from {', '.join(BROWSERS)}") from None
    d = mac if sys.platform == "darwin" else linux
    if not d.exists():
        raise BrowserCookieError(f"{browser}: no user-data directory at {d}")
    return d


def _cookie_dbs(browser: str, profile: Optional[str] = None) -> list[Path]:
    """Cookie sqlite files, requested/Default profile first, then the others."""
    root = _user_data_dir(browser)
    names = [profile] if profile else ["Default"]
    names += sorted(p.name for p in root.iterdir() if p.is_dir() and p.name.startswith("Profile "))
    out: list[Path] = []
    for n in names:
        for cand in (root / n / "Cookies", root / n / "Network" / "Cookies"):
            if cand.exists() and cand not in out:
                out.append(cand)
    if not out:
        raise BrowserCookieError(f"{browser}: no Cookies database found under {root}"
                                 + (f" for profile {profile!r}" if profile else ""))
    return out


def _derive_key(browser: str) -> bytes:
    if sys.platform == "darwin":
        service = BROWSERS[browser][2]
        try:
            pw = subprocess.run(["security", "find-generic-password", "-s", service, "-w"],
                                capture_output=True, text=True, check=True).stdout.strip()
        except subprocess.CalledProcessError as e:
            raise BrowserCookieError(
                f"could not read {service!r} from the keychain (exit {e.returncode}). "
                "macOS should have prompted for access; click 'Always Allow'.") from None
        return hashlib.pbkdf2_hmac("sha1", pw.encode(), SALT, 1003, 16)
    return hashlib.pbkdf2_hmac("sha1", b"peanuts", SALT, 1, 16)


def _aes_cbc_decrypt(key: bytes, data: bytes) -> bytes:
    """AES-128-CBC + PKCS7 via the system openssl (no AES in the stdlib)."""
    try:
        r = subprocess.run(["openssl", "enc", "-d", "-aes-128-cbc", "-nosalt",
                            "-K", key.hex(), "-iv", IV.hex()],
                           input=data, capture_output=True, check=True)
    except FileNotFoundError:
        raise BrowserCookieError("`openssl` binary not found; needed to decrypt browser cookies") from None
    except subprocess.CalledProcessError as e:
        raise BrowserCookieError(f"openssl failed to decrypt a cookie: {e.stderr.decode(errors='replace').strip()}") from None
    return r.stdout


def decrypt_value(key: bytes, encrypted: bytes, host_key: str) -> str:
    if not encrypted.startswith(b"v10"):
        raise BrowserCookieError(f"unsupported cookie encryption prefix {encrypted[:3]!r}")
    plain = _aes_cbc_decrypt(key, encrypted[3:])
    # Chrome ≥ 130 prepends sha256(host_key) to bind the value to its domain.
    if len(plain) >= 32 and plain[:32] == hashlib.sha256(host_key.encode()).digest():
        plain = plain[32:]
    return plain.decode(errors="replace")


def read_cookies(browser: str = "chrome", host: str = "leetcode.com",
                 profile: Optional[str] = None, names: Optional[set[str]] = None) -> dict[str, str]:
    """Return {cookie_name: value} for `host` (and `.host`) from the first profile
    that has any. Cookies are decrypted lazily, so the keychain is only touched
    when a matching cookie exists."""
    hosts = (host, "." + host)
    key: Optional[bytes] = None
    for db in _cookie_dbs(browser, profile):
        rows = _query(db, hosts)
        if names:
            rows = [r for r in rows if r[0] in names]
        if not rows:
            continue
        out: dict[str, str] = {}
        for name, value, enc, host_key in rows:
            if value:
                out[name] = value
            elif enc:
                if key is None:
                    key = _derive_key(browser)
                out[name] = decrypt_value(key, bytes(enc), host_key)
        if out:
            return out
    raise BrowserCookieError(f"{browser}: no {host} cookies found. Are you logged in there?")


def _query(db: Path, hosts: tuple[str, ...]) -> list[tuple]:
    # The browser holds a lock on the live DB; copy it (plus its WAL) first.
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / "Cookies"
        shutil.copy2(db, copy)
        for suffix in ("-wal", "-shm", "-journal"):
            side = db.with_name(db.name + suffix)
            if side.exists():
                shutil.copy2(side, copy.with_name(copy.name + suffix))
        con = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            marks = ",".join("?" * len(hosts))
            return con.execute(
                f"SELECT name, value, encrypted_value, host_key FROM cookies "
                f"WHERE host_key IN ({marks}) ORDER BY expires_utc DESC", hosts).fetchall()
        except sqlite3.DatabaseError as e:
            raise BrowserCookieError(f"could not read {db}: {e}") from None
        finally:
            con.close()
