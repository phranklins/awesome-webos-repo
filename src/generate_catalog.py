#!/usr/bin/env python3
"""Build dist/repo.json for the Homebrew Channel from catalog/apps.yml.

Each app is fetched independently. Failures are logged and skipped so one
broken upstream does not stop the rest of the catalog.

Long notices and body text go in descriptions/*.html via fullDescriptionUrl
so Homebrew Channel does not clip them in the details view.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
import urllib.error
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

sys.path.insert(0, str(Path(__file__).resolve().parent))

from http_util import absolute_url, fetch_json  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_APPS = ROOT / "catalog" / "apps.yml"
DEFAULT_OUT = ROOT / "dist" / "repo.json"
DEFAULT_DESCRIPTIONS = ROOT / "descriptions"
DEFAULT_REPO_SCHEMA = ROOT / "schemas" / "HomebrewRepository.schema.json"
DEFAULT_MANIFEST_SCHEMA = ROOT / "schemas" / "HomebrewPackageManifest.schema.json"

log = logging.getLogger("generate_catalog")


def load_apps_config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "apps" not in data:
        raise SystemExit(f"{path} must contain an 'apps' list")
    return data


def notice_text(app: dict[str, Any], config: dict[str, Any]) -> str | None:
    notice = app.get("notice")
    if notice == "youtube_collision":
        return config.get("youtube_collision_note")
    if isinstance(notice, str) and notice.strip():
        return notice.strip()
    return None


def description_slug(app: dict[str, Any]) -> str:
    """Stable unique filename stem (package id can collide, e.g. YouTube forks)."""
    if app.get("slug"):
        return str(app["slug"])
    raw = app.get("title") or app.get("name") or app.get("id") or "app"
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", str(raw)).strip("-").lower()
    return slug or "app"


def html_escape_paragraphs(text: str) -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    if not parts:
        parts = [text.strip()]
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in parts)


def write_description_html(
    *,
    path: Path,
    notice: str | None,
    body: str | None,
    source_url: str | None,
) -> None:
    chunks: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Description</title>",
        "<style>",
        "body { margin: 24px 28px; font-family: sans-serif; line-height: 1.45; }",
        "p { margin: 0 0 1em; }",
        ".notice { margin-bottom: 1.25em; }",
        "</style>",
        "</head>",
        "<body>",
    ]
    if notice:
        chunks.append(f'<div class="notice"><p><strong>{html.escape(notice)}</strong></p></div>')
    if body:
        chunks.append(html_escape_paragraphs(body))
    if source_url:
        chunks.append(
            f'<p>Project page: <a href="{html.escape(source_url, quote=True)}">'
            f"{html.escape(source_url)}</a></p>"
        )
    if not notice and not body:
        chunks.append("<p>No additional description is available for this app.</p>")
    chunks.extend(["</body>", "</html>", ""])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(chunks), encoding="utf-8")


def package_from_manifest(
    manifest: dict[str, Any],
    *,
    manifest_url: str | None,
    title_override: str | None,
    short_description: str | None,
    full_description_url: str | None,
) -> dict[str, Any]:
    title = title_override or manifest.get("title")
    icon = manifest.get("iconUri")
    pkg_id = manifest.get("id")
    if not pkg_id or not title or not icon:
        raise ValueError("manifest missing required id/title/iconUri")

    resolved = dict(manifest)
    if manifest_url and resolved.get("ipkUrl"):
        resolved["ipkUrl"] = absolute_url(manifest_url, resolved["ipkUrl"])

    package: dict[str, Any] = {
        "id": pkg_id,
        "title": title,
        "iconUri": icon,
        "manifest": resolved,
    }
    if short_description:
        package["shortDescription"] = short_description
    elif manifest.get("appDescription"):
        package["shortDescription"] = manifest["appDescription"]
    if full_description_url:
        package["fullDescriptionUrl"] = full_description_url
    return package


def extract_from_repo_json(
    repo: dict[str, Any],
    package_id: str,
    repo_url: str,
) -> tuple[dict[str, Any], str | None, dict[str, Any]]:
    packages = repo.get("packages")
    if not isinstance(packages, list):
        raise ValueError("repo JSON has no packages array")

    matches = [p for p in packages if isinstance(p, dict) and p.get("id") == package_id]
    if not matches:
        raise ValueError(f"package id {package_id!r} not found in {repo_url}")
    entry = matches[0]

    if entry.get("manifest") and isinstance(entry["manifest"], dict):
        return entry["manifest"], None, entry

    manifest_url = entry.get("manifestUrl")
    if not manifest_url:
        raise ValueError(f"{package_id}: repo entry has neither manifest nor manifestUrl")
    manifest_url = absolute_url(repo_url, manifest_url)
    assert manifest_url is not None
    return fetch_json(manifest_url), manifest_url, entry


def build_package(
    app: dict[str, Any],
    config: dict[str, Any],
    *,
    descriptions_dir: Path,
) -> dict[str, Any]:
    source = app.get("source") or {}
    source_type = source.get("type")
    package_id = app["id"]
    title_override = app.get("title")
    notice = notice_text(app, config)
    base = (config.get("catalog_base_url") or "").rstrip("/")
    if not base:
        raise ValueError("catalog_base_url is required in apps.yml")

    slug = description_slug(app)
    rel_html = f"descriptions/{slug}.html"
    full_description_url = f"{base}/{rel_html}"
    html_path = descriptions_dir / f"{slug}.html"

    repo_entry: dict[str, Any] = {}
    manifest: dict[str, Any]
    manifest_url: str | None

    if source_type == "manifest_url":
        url = source["url"]
        manifest = fetch_json(url)
        manifest_url = url
        if manifest.get("id") and manifest["id"] != package_id:
            raise ValueError(
                f"manifest id {manifest.get('id')!r} does not match expected {package_id!r}"
            )
    elif source_type == "repo_json":
        url = source["url"]
        repo = fetch_json(url)
        manifest, manifest_url, repo_entry = extract_from_repo_json(repo, package_id, url)
        if manifest.get("id") and manifest["id"] != package_id:
            raise ValueError(
                f"manifest id {manifest.get('id')!r} does not match expected {package_id!r}"
            )
        if not manifest.get("iconUri") and repo_entry.get("iconUri"):
            manifest = {**manifest, "iconUri": repo_entry["iconUri"]}
    else:
        raise ValueError(f"unknown source.type {source_type!r}")

    short = (
        repo_entry.get("shortDescription")
        or manifest.get("appDescription")
        or app.get("shortDescription")
    )
    if isinstance(short, str):
        short = " ".join(short.split())
        if len(short) > 120:
            short = short[:117].rstrip() + "..."

    body = repo_entry.get("shortDescription") or manifest.get("appDescription") or short
    source_link = app.get("repository") or manifest.get("sourceUrl")
    write_description_html(
        path=html_path,
        notice=notice,
        body=body if isinstance(body, str) else None,
        source_url=source_link if isinstance(source_link, str) else None,
    )

    return package_from_manifest(
        manifest,
        manifest_url=manifest_url,
        title_override=title_override,
        short_description=short if isinstance(short, str) else None,
        full_description_url=full_description_url,
    )


def validate_repo(repo: dict[str, Any], repo_schema_path: Path, manifest_schema_path: Path) -> None:
    repo_schema = json.loads(repo_schema_path.read_text(encoding="utf-8"))
    manifest_schema = json.loads(manifest_schema_path.read_text(encoding="utf-8"))

    resources = [
        (repo_schema.get("$id") or "HomebrewRepository.schema", repo_schema),
        (manifest_schema.get("$id") or "HomebrewPackageManifest.schema", manifest_schema),
        ("HomebrewPackageManifest.schema", manifest_schema),
        ("https://webosbrew.org/schema/HomebrewPackageManifest.schema", manifest_schema),
    ]
    registry = Registry()
    for uri, schema in resources:
        registry = registry.with_resource(uri, Resource.from_contents(schema))

    Draft202012Validator(repo_schema, registry=registry).validate(repo)

    manifest_validator = Draft202012Validator(manifest_schema)
    for pkg in repo.get("packages") or []:
        if "manifest" in pkg:
            manifest_validator.validate(pkg["manifest"])


def generate(
    apps_path: Path,
    out_path: Path,
    repo_schema_path: Path,
    manifest_schema_path: Path,
    descriptions_dir: Path,
) -> int:
    config = load_apps_config(apps_path)
    apps = config["apps"]
    packages: list[dict[str, Any]] = []
    failures: list[str] = []
    seen_ids: dict[str, str] = {}
    written_slugs: set[str] = set()

    descriptions_dir.mkdir(parents=True, exist_ok=True)

    for app in apps:
        name = app.get("name", app.get("id", "?"))
        pkg_id = app.get("id", "?")
        try:
            package = build_package(app, config, descriptions_dir=descriptions_dir)
            slug = description_slug(app)
            if slug in written_slugs:
                raise ValueError(f"duplicate description slug {slug!r}")
            written_slugs.add(slug)
            if pkg_id in seen_ids:
                log.warning(
                    "Duplicate package id %s (%s and %s). Channel may only show one; "
                    "kept both entries as configured.",
                    pkg_id,
                    seen_ids[pkg_id],
                    name,
                )
            seen_ids[pkg_id] = name
            packages.append(package)
            log.info("OK  %s (%s) -> %s", name, package["id"], package.get("fullDescriptionUrl"))
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ) as exc:
            msg = f"SKIP {name} ({pkg_id}): {exc}"
            log.error(msg)
            failures.append(msg)

    for path in descriptions_dir.glob("*.html"):
        if path.stem not in written_slugs:
            log.info("Removing stale description %s", path.name)
            path.unlink()

    packages.sort(key=lambda package: str(package.get("title", "")).casefold())
    repo = {"packages": packages}
    validate_repo(repo, repo_schema_path, manifest_schema_path)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(repo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.info("Wrote %s with %d packages (%d skipped)", out_path, len(packages), len(failures))

    if failures:
        log.error("Failures:\n%s", "\n".join(failures))
    return 0 if packages else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apps", type=Path, default=DEFAULT_APPS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--descriptions", type=Path, default=DEFAULT_DESCRIPTIONS)
    parser.add_argument("--repo-schema", type=Path, default=DEFAULT_REPO_SCHEMA)
    parser.add_argument("--manifest-schema", type=Path, default=DEFAULT_MANIFEST_SCHEMA)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    return generate(
        args.apps,
        args.out,
        args.repo_schema,
        args.manifest_schema,
        args.descriptions,
    )


if __name__ == "__main__":
    sys.exit(main())
