#!/usr/bin/env python3
"""Sync catalog/apps.yml from awesome-webos + official Channel catalog.

Quietly:
  - adds newly packaged community apps
  - refreshes notices/names (preserves explicit title overrides)
  - removes broken sources that cannot be repaired
  - removes apps whose id is now in the official catalog
  - re-probes Incomplete awesome-webos entries every run
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from channel_probe import (  # noqa: E402
    is_non_channel_entry,
    normalize_github_repo,
    probe_github_project,
    source_url_works,
)
from http_util import fetch_json, fetch_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPS = ROOT / "catalog" / "apps.yml"
AWESOME_README = "https://raw.githubusercontent.com/tolgakurtuluss/awesome-webos/main/README.md"
OFFICIAL_APPS = "https://repo.webosbrew.org/api/apps.json"

log = logging.getLogger("sync_awesome_webos")

ENTRY_RE = re.compile(
    r"^- \[([^\]]+)\]\(([^)]+)\)\s*-\s*(.+)$"
)


def parse_awesome_apps(readme: str) -> list[dict[str, str]]:
    start = readme.find("\n## Apps\n")
    if start < 0:
        start = readme.find("## Apps\n")
    end = readme.find("\n## Community\n", start if start >= 0 else 0)
    if start < 0 or end < 0:
        raise SystemExit("Could not find ## Apps / ## Community sections in awesome-webos README")
    section = readme[start:end]
    entries: list[dict[str, str]] = []
    for line in section.splitlines():
        m = ENTRY_RE.match(line.strip())
        if not m:
            continue
        name, url, desc = m.group(1), m.group(2), m.group(3)
        desc = re.sub(r"\s*!\[Stars\].*$", "", desc).strip().rstrip(".")
        entries.append({"name": name, "url": url, "description": desc})
    return entries


def official_package_ids() -> set[str]:
    data = fetch_json(OFFICIAL_APPS)
    packages = data.get("packages") or []
    return {p["id"] for p in packages if isinstance(p, dict) and p.get("id")}


def load_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "apps" not in data:
        raise SystemExit(f"{path} must contain an apps list")
    data["apps"] = list(data.get("apps") or [])
    return data


def write_config(path: Path, config: dict[str, Any]) -> None:
    header = (
        "# Source list for the awesome-webos Homebrew Channel catalog.\n"
        "# Only apps missing from the official Channel catalog (repo.webosbrew.org).\n"
        "# Maintained by src/sync_awesome_webos.py — prefer editing via sync rules.\n"
        "\n"
    )
    # Stable key order for readability
    ordered: dict[str, Any] = {}
    for key in ("catalog_base_url", "youtube_collision_note"):
        if key in config:
            ordered[key] = config[key]
    for key, value in config.items():
        if key in ordered or key == "apps":
            continue
        ordered[key] = value
    # Sort by the displayed title when present, otherwise by the app name.
    ordered["apps"] = sorted(
        config["apps"],
        key=lambda app: str(app.get("title") or app.get("name", "")).casefold(),
    )

    body = yaml.safe_dump(
        ordered,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=100,
    )
    path.write_text(header + body, encoding="utf-8")


def repo_key(url: str) -> str | None:
    return normalize_github_repo(url)


def index_awesome_by_repo(entries: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for e in entries:
        key = repo_key(e["url"])
        if key:
            out[key] = e
    return out


def notice_from_description(description: str, package_id: str) -> tuple[str, str | None]:
    """Return (label, notice) derived from awesome blurb / package id."""
    if package_id == "youtube.leanback.v4":
        return "needs_notice", "youtube_collision"

    text = (description or "").lower()
    notices: list[str] = []

    if re.search(r"\broot(ed|ing)?\b", text) or "homebrew channel" in text and "require" in text:
        if "root" in text:
            notices.append("Requires a rooted TV (or root for full features). Read the project README.")
    if "usb" in text:
        notices.append("External USB storage may be required. Read the project README.")
    if "own the game" in text or "provide the assets" in text or "game assets" in text:
        notices.append("Requires game assets you already own. Read the project README before installing.")
    if "cloudstream" in text:
        notices.append(
            "Runs CloudStream extensions. You are responsible for what you install and for following applicable laws."
        )
    if "alpha" in text or "pre-release" in text or "beta" in text:
        notices.append("May be alpha/beta software. Expect breakage.")
    if "multiple" in text and "ipk" in text:
        notices.append(
            "Multiple IPK variants may exist; check the project README for your TV."
        )

    if notices:
        # Keep a single concise notice string
        return "needs_notice", notices[0]
    return "packaged", None


def apply_notice_fields(entry: dict[str, Any], label: str, notice: str | None) -> bool:
    changed = False
    if entry.get("label") != label:
        entry["label"] = label
        changed = True
    if notice:
        if entry.get("notice") != notice:
            entry["notice"] = notice
            changed = True
    else:
        if "notice" in entry:
            del entry["notice"]
            changed = True
    return changed


def sync(apps_path: Path) -> int:
    config = load_config(apps_path)
    apps: list[dict[str, Any]] = config["apps"]

    log.info("Fetching awesome-webos README…")
    awesome_entries = parse_awesome_apps(fetch_text(AWESOME_README))
    awesome_by_repo = index_awesome_by_repo(awesome_entries)
    log.info("awesome-webos Apps entries: %d", len(awesome_entries))

    log.info("Fetching official Channel catalog…")
    official_ids = official_package_ids()
    log.info("official packages: %d", len(official_ids))

    existing_by_repo: dict[str, dict[str, Any]] = {}
    for app in apps:
        key = repo_key(app.get("repository") or "")
        if key:
            existing_by_repo[key] = app

    kept: list[dict[str, Any]] = []
    removed = 0
    refreshed = 0
    repaired = 0

    # --- Pass existing apps: remove official / broken; refresh metadata ---
    for app in apps:
        name = app.get("name", app.get("id", "?"))
        pkg_id = app.get("id")
        repo = app.get("repository") or ""
        key = repo_key(repo)

        if pkg_id and pkg_id in official_ids:
            # Intentional forks (e.g. YouTube Foxtended) share an official package id
            # but remain in this community catalog with a collision notice.
            if app.get("notice") == "youtube_collision":
                log.info(
                    "KEEP %s (%s): fork of an official package id (collision notice)",
                    name,
                    pkg_id,
                )
            else:
                log.info("REMOVE %s (%s): now in official catalog", name, pkg_id)
                removed += 1
                continue

        source = app.get("source") or {}
        works = bool(pkg_id) and source_url_works(source, str(pkg_id))
        if not works:
            log.info("Broken source for %s — probing for replacement…", name)
            probe = probe_github_project(repo, prefer_id=str(pkg_id) if pkg_id else None)
            if probe and probe["id"] not in official_ids:
                app["id"] = probe["id"]
                app["source"] = {"type": probe["type"], "url": probe["url"]}
                log.info(
                    "REPAIR %s: %s %s",
                    name,
                    probe["type"],
                    probe["url"],
                )
                repaired += 1
                works = True
            else:
                log.info("REMOVE %s (%s): broken source and no replacement", name, pkg_id)
                removed += 1
                continue

        # Refresh name / notice from awesome-webos when linked
        awesome = awesome_by_repo.get(key or "")
        if awesome:
            new_name = awesome["name"]
            if app.get("name") != new_name:
                app["name"] = new_name
                refreshed += 1
            label, notice = notice_from_description(awesome["description"], str(app.get("id")))
            if apply_notice_fields(app, label, notice):
                refreshed += 1
            # title only if no explicit override
            # (explicit title key present means preserve)
        else:
            # Still refresh YouTube collision notice by id
            if app.get("id") == "youtube.leanback.v4":
                if apply_notice_fields(app, "needs_notice", "youtube_collision"):
                    refreshed += 1

        kept.append(app)

    # --- Probe awesome entries not yet in catalog ---
    added = 0
    skipped = 0
    catalog_repos = {repo_key(a.get("repository") or "") for a in kept}

    for entry in awesome_entries:
        name, url, desc = entry["name"], entry["url"], entry["description"]
        reason = is_non_channel_entry(name, url, desc)
        if reason:
            log.info("SKIP %s: %s", name, reason)
            skipped += 1
            continue

        key = repo_key(url)
        if not key:
            log.info("SKIP %s: no GitHub repository link", name)
            skipped += 1
            continue
        if key in catalog_repos:
            continue

        # Official page links already filtered; still skip if we somehow resolve to official id
        probe = probe_github_project(url)
        if not probe:
            log.info("SKIP %s: no Channel packaging found (Incomplete)", name)
            skipped += 1
            continue

        label, notice = notice_from_description(desc, probe["id"])
        if probe["id"] in official_ids and notice != "youtube_collision":
            log.info("SKIP %s (%s): official catalog overlap", name, probe["id"])
            skipped += 1
            continue

        new_app: dict[str, Any] = {
            "name": name,
            "id": probe["id"],
            "repository": f"https://github.com/{key.split('/')[0]}/{url.rstrip('/').split('/')[-1]}"
            if "github.com" in url
            else url.split("/tree/")[0],
            "label": label,
            "source": {"type": probe["type"], "url": probe["url"]},
        }
        # Prefer canonical github URL without tree paths
        gh = re.match(r"(https://github.com/[^/]+/[^/#?]+)", url)
        if gh:
            new_app["repository"] = gh.group(1).rstrip("/")

        if notice:
            new_app["notice"] = notice

        kept.append(new_app)
        catalog_repos.add(key)
        added += 1
        log.info(
            "ADD %s (%s) via %s %s",
            name,
            probe["id"],
            probe["type"],
            probe["url"],
        )

    config["apps"] = kept
    write_config(apps_path, config)
    log.info(
        "Sync done: %d apps (added=%d removed=%d repaired=%d refresh_touches=%d skipped=%d)",
        len(kept),
        added,
        removed,
        repaired,
        refreshed,
        skipped,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    return sync(args.apps)


if __name__ == "__main__":
    sys.exit(main())
