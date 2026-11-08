# awesome-webos Homebrew Channel catalog

A single Homebrew Channel repository built from community apps listed in [awesome-webos](https://github.com/tolgakurtuluss/awesome-webos) that are **not** already in the official [webosbrew catalog](https://repo.webosbrew.org/).

Add one URL in the Channel instead of adding each app’s repository separately.

## Add this catalog on your TV

1. Open **Homebrew Channel** → **Settings**.
2. Choose **Add repository**.
3. Paste this URL (after this project is on GitHub under your account, replace `OWNER` / `REPO`):

```text
https://raw.githubusercontent.com/OWNER/REPO/main/dist/repo.json
```

4. Go back to the apps list and refresh.

There is no GitHub Pages site — the Channel reads the JSON file directly from GitHub, the same way many homebrew projects document their own repos.

## What is included (and why)

v1 includes community apps from awesome-webos that:

- are installable through the Homebrew Channel format, and
- are **missing** from the official Channel catalog.

Apps that need root, extra game files, or other special setup are included with a short warning in the description.

Apps already on [repo.webosbrew.org](https://repo.webosbrew.org/) are **not** duplicated here.

### YouTube forks (same app id)

Three YouTube homebrew builds share the package id `youtube.leanback.v4`:

| Name | In this catalog? |
|---|---|
| webosbrew YouTube AdFree | No (already official) |
| youtube-webos (NicholasBly) | Yes |
| **YouTube Foxtended** (foxi69) | Yes |

**Only one of these three can be installed at a time.** Installing another replaces or conflicts with the one you already have. Uninstall the official LG YouTube app before installing any of them.

Because both forks share the same package id, the Homebrew Channel UI may only show one of the two catalog rows. The collision note is still written into both entries in `dist/repo.json`.

## How to run the generator (on your Mac)

```bash
cd /path/to/this/repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python src/generate_catalog.py -v
```

That writes `dist/repo.json`. GitHub Actions also regenerates it on push and on a daily schedule, then commits the file when it changes.

## How to add an app

1. Confirm it is **not** already listed at https://repo.webosbrew.org/api/apps.json.
2. Confirm it has a Channel-usable `.manifest.json` **or** its own `apps.json` / `repo.json`.
3. Add an entry under `apps:` in [`catalog/apps.yml`](catalog/apps.yml) with:
   - `name`, `id`, `repository`, `label` (`packaged` or `needs_notice`)
   - `source.type`: `manifest_url` or `repo_json`
   - `source.url`: the verified URL
   - optional `title` override and `notice` text
4. Run the generator locally and check that the app appears in `dist/repo.json`.
5. Open a pull request.

Do not guess package ids or URLs. If a fetch fails, the generator skips that app and keeps the rest.

## What's in this folder

- `catalog/apps.yml` — checked-in source list (edit this to change the catalog)
- `src/generate_catalog.py` — builds `dist/repo.json`
- `dist/repo.json` — file the Homebrew Channel should download
- `schemas/` — Homebrew Channel JSON schemas used for validation
- `.github/workflows/generate-catalog.yml` — regenerates the catalog on a schedule

## Status

- [x] First generator run producing a validated `dist/repo.json`
- [ ] Published on GitHub with a working raw URL
- [ ] Tested “Add repository” on a TV

## Notes

This project is independent community tooling. It is not affiliated with LG Electronics or the webosbrew maintainers. Inclusion is not a security audit. Read [awesome-webos SAFETY.md](https://github.com/tolgakurtuluss/awesome-webos/blob/main/SAFETY.md) before installing homebrew on a TV.
