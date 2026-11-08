"""Shared HTTP helpers for catalog scripts."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlparse

USER_AGENT = "awesome-webos-catalog/1.0 (+https://github.com/phranklins/awesome-webos-repo)"
TIMEOUT_SECONDS = 45


def absolute_url(base: str, maybe_relative: str | None) -> str | None:
    if not maybe_relative:
        return maybe_relative
    if urlparse(maybe_relative).scheme:
        return maybe_relative
    return urljoin(base, maybe_relative)


def fetch_bytes(url: str, *, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": accept},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
        return resp.read()


def fetch_text(url: str, *, accept: str = "text/plain,*/*") -> str:
    raw = fetch_bytes(url, accept=accept)
    return raw.decode("utf-8", errors="replace")


def fetch_json(url: str) -> Any:
    raw = fetch_bytes(url, accept="application/json,text/plain,*/*")
    return json.loads(raw.decode("utf-8", errors="replace"))


def fetch_ok(url: str) -> bool:
    try:
        fetch_bytes(url)
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False
