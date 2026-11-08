"""Probe a GitHub (or linked) project for Homebrew Channel package metadata."""

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlparse

from http_util import fetch_json, fetch_ok, fetch_text

log = logging.getLogger("channel_probe")

GITHUB_REPO_RE = re.compile(r"https?://github\.com/([^/\s]+)/([^/\s?#]+)", re.I)
COMMON_REPO_PATHS = (
    "repo/apps.json",
    "apps.json",
    "repo.json",
    "dist/repo.json",
    "dist/apps.json",
    "docs/manifest.json",
    "channel/apps.json",
    "homebrew/apps.json",
    "homebrew/repo.json",
)


def normalize_github_repo(url: str) -> str | None:
    m = GITHUB_REPO_RE.search(url or "")
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if repo.endswith(".git"):
        repo = repo[:-4]
    return f"{owner}/{repo}".lower()


def github_owner_repo(url: str) -> tuple[str, str] | None:
    key = normalize_github_repo(url)
    if not key:
        return None
    owner, repo = key.split("/", 1)
    return owner, repo


def looks_like_channel_repo(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("packages"), list)


def looks_like_manifest(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    required = ("id", "version", "type", "title", "iconUri", "ipkUrl", "ipkHash")
    return all(k in data for k in required) and isinstance(data.get("ipkHash"), dict)


def package_id_from_payload(data: dict[str, Any], prefer_id: str | None = None) -> str | None:
    if looks_like_manifest(data):
        return str(data.get("id")) if data.get("id") else None
    if looks_like_channel_repo(data):
        packages = data["packages"]
        if prefer_id:
            for pkg in packages:
                if isinstance(pkg, dict) and pkg.get("id") == prefer_id:
                    return prefer_id
        if len(packages) == 1 and isinstance(packages[0], dict) and packages[0].get("id"):
            return str(packages[0]["id"])
        # Multi-package repo: prefer a package whose sourceUrl/repository matches later.
        for pkg in packages:
            if isinstance(pkg, dict) and pkg.get("id"):
                return str(pkg["id"])
    return None


def extract_channel_urls_from_text(text: str) -> list[str]:
    urls = set()
    for m in re.finditer(r"https?://[^\s\)\"\'<>]+", text or ""):
        u = m.group(0).rstrip(".,);]")
        lower = u.lower()
        if any(
            x in lower
            for x in (
                "apps.json",
                "repo.json",
                "manifest.json",
                "/homebrew/",
                "hbc-repo",
            )
        ):
            urls.add(u)
    return sorted(urls)


def try_channel_json(url: str) -> dict[str, Any] | None:
    try:
        data = fetch_json(url)
    except Exception as exc:  # noqa: BLE001 — probe should never abort sync
        log.debug("probe fetch failed %s: %s", url, exc)
        return None
    if looks_like_channel_repo(data) or looks_like_manifest(data):
        return data
    return None


def probe_github_project(
    repository: str,
    *,
    prefer_id: str | None = None,
) -> dict[str, Any] | None:
    """Return {type, url, id, data} or None if no Channel packaging found."""
    parsed = github_owner_repo(repository)
    if not parsed:
        return None
    owner, repo = parsed

    candidates: list[str] = []

    # Project README on main/master
    readme = None
    for branch in ("main", "master"):
        try:
            readme = fetch_text(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/README.md")
            break
        except Exception:
            continue
    if readme:
        candidates.extend(extract_channel_urls_from_text(readme))

    for path in COMMON_REPO_PATHS:
        for branch in ("main", "master"):
            candidates.append(f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}")

    # Special branches seen in the wild
    candidates.extend(
        [
            f"https://raw.githubusercontent.com/{owner}/{repo}/homebrew/repo.json",
            f"https://raw.githubusercontent.com/{owner}/{repo}/homebrew-repo/apps.json",
            f"https://raw.githubusercontent.com/{owner}/{repo}/hbc-repo/stable/apps.json",
        ]
    )

    # GitHub releases
    releases: list[dict[str, Any]] = []
    try:
        latest = fetch_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        )
        if isinstance(latest, dict):
            releases.append(latest)
    except Exception:
        try:
            releases = fetch_json(
                f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=5"
            )
            if not isinstance(releases, list):
                releases = []
        except Exception:
            releases = []

    for rel in releases:
        tag = rel.get("tag_name") or ""
        for asset in rel.get("assets") or []:
            name = asset.get("name") or ""
            dl = asset.get("browser_download_url")
            if not dl:
                continue
            if name in ("repo.json", "apps.json") or name.endswith("repo.json") or name.endswith("apps.json"):
                candidates.append(dl)
                if tag:
                    candidates.append(
                        f"https://github.com/{owner}/{repo}/releases/latest/download/{name}"
                    )
            if name.endswith(".manifest.json") or name == "manifest.json":
                # Need an IPK in the same release for "packaged"
                ipks = [
                    a.get("name")
                    for a in (rel.get("assets") or [])
                    if (a.get("name") or "").endswith(".ipk")
                ]
                if ipks:
                    candidates.append(dl)
                    candidates.append(
                        f"https://github.com/{owner}/{repo}/releases/latest/download/{name}"
                    )

    # Dedupe preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    for url in ordered:
        data = try_channel_json(url)
        if not data:
            continue
        pkg_id = package_id_from_payload(data, prefer_id=prefer_id)
        if not pkg_id:
            continue
        if looks_like_channel_repo(data):
            return {"type": "repo_json", "url": url, "id": pkg_id, "data": data}
        if looks_like_manifest(data):
            # Prefer latest/download form when possible
            source_url = url
            if "/releases/download/" in url and "/releases/latest/download/" not in url:
                asset = url.rsplit("/", 1)[-1]
                latest_url = (
                    f"https://github.com/{owner}/{repo}/releases/latest/download/{asset}"
                )
                if fetch_ok(latest_url):
                    source_url = latest_url
            return {"type": "manifest_url", "url": source_url, "id": pkg_id, "data": data}
    return None


def source_url_works(source: dict[str, Any], package_id: str) -> bool:
    url = (source or {}).get("url")
    stype = (source or {}).get("type")
    if not url or not stype:
        return False
    data = try_channel_json(url)
    if not data:
        return False
    if stype == "manifest_url":
        return looks_like_manifest(data) and data.get("id") == package_id
    if stype == "repo_json":
        if not looks_like_channel_repo(data):
            return False
        return any(
            isinstance(p, dict) and p.get("id") == package_id for p in data.get("packages") or []
        )
    return False


def is_non_channel_entry(name: str, url: str, description: str) -> str | None:
    """Return skip reason if this awesome entry is not a TV Channel app candidate."""
    lower_url = (url or "").lower()
    lower_desc = (description or "").lower()
    lower_name = (name or "").lower()
    blob = f"{lower_name} {lower_desc}"

    if "repo.webosbrew.org/apps/" in lower_url:
        return "official catalog page"
    if not GITHUB_REPO_RE.search(url or "") and "github.io" not in lower_url:
        # Non-GitHub without github pages — still allow if URL itself is apps.json later
        if not lower_url.endswith(".json"):
            if any(x in lower_url for x in ("reddit.com", "wikipedia.org", "webostv.developer")):
                return "not a project repository"
            if lower_url.endswith("/") or "cani.rootmy.tv" in lower_url:
                return "website / guide"

    # Non-TV clients hosted outside the TV (phone/desktop apps), not "controls a Windows PC from the TV".
    if any(
        x in blob
        for x in (
            "android app for controlling",
            "android remote for lg",
            "windows utility that",
            "self-hosted web remote that finds",
            "dns blocklist",
            "blocklists for filtering",
        )
    ):
        return "desktop/mobile/non-TV tool"
    if lower_name in ("lg remote", "lgpower", "lgtv companion") or (
        lower_name == "hearth" and "mutaaf" in lower_url
    ):
        return "desktop/mobile/non-TV tool"

    if any(
        x in blob
        for x in (
            "rooting project",
            "autoroot",
            "checks whether your tv model",
            "ssap tooling",
        )
    ) and "homebrew channel" not in blob:
        # Rooting tools without being a Channel package
        if "ipk" not in blob and "homebrew" not in blob:
            return "rooting / tooling guide"

    host = urlparse(url).netloc.lower()
    if host.endswith("apk") or lower_url.endswith(".apk"):
        return "android package link"

    return None
