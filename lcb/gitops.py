"""Minimal git helper: commit the solution + progress after a submission."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .config import ROOT


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)


def is_repo() -> bool:
    return _git("rev-parse", "--is-inside-work-tree").returncode == 0


def commit(paths: list[Path], message: str) -> str | None:
    if not is_repo():
        return None
    rel = [str(p.relative_to(ROOT)) if p.is_absolute() else str(p) for p in paths]
    _git("add", "--", *rel)
    if _git("diff", "--cached", "--quiet").returncode == 0:
        return None  # nothing staged
    r = _git("commit", "-q", "-m", message)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return _git("rev-parse", "--short", "HEAD").stdout.strip()


def push() -> str | None:
    """Push the current branch to its upstream (or origin) if a remote exists. Returns a short status."""
    if not is_repo() or _git("remote").stdout.strip() == "":
        return None
    r = _git("push", "-q")
    if r.returncode != 0:
        r = _git("push", "-q", "-u", "origin", "HEAD")
    return "pushed" if r.returncode == 0 else f"push failed: {r.stderr.strip()[:200]}"
