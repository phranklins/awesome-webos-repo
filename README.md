# awesome-webos Homebrew Channel catalog

One Homebrew Channel repository for community webOS apps from [awesome-webos](https://github.com/tolgakurtuluss/awesome-webos) that are **not** already in the official [webosbrew catalog](https://repo.webosbrew.org/).

Add this single URL in the Channel instead of adding each app’s repository separately.

## Add this catalog on your TV

1. Open **Homebrew Channel** → **Settings**.
2. Choose **Add repository**.
3. Paste:

```text
https://phranklins.github.io/awesome-webos-repo/repo.json
```

That address is refreshed whenever the catalog file changes. If you already added the longer `raw.githubusercontent.com` link, you can keep it.

4. Go back to the apps list and refresh.

## What is included (and why)

This catalog lists community apps from awesome-webos that:

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

Because both forks share the same package id, the Homebrew Channel UI may only show one of the two catalog rows.

## How to add an app

Do **not** open a pull request against this catalog repo to request a new app.

1. Add (or update) the project on [awesome-webos](https://github.com/tolgakurtuluss/awesome-webos) by following that project’s [CONTRIBUTING.md](https://github.com/tolgakurtuluss/awesome-webos/blob/main/CONTRIBUTING.md).
2. Once it is on the awesome-webos list **and** publishes a Homebrew Channel–usable package (its own `apps.json` / `repo.json`, or a release `.manifest.json` + IPK), this repo’s daily Action discovers it and publishes it automatically.

The same daily sync will also:

- refresh short warning notes when the awesome-webos description changes,
- drop apps that join the [official Channel catalog](https://repo.webosbrew.org/),
- drop apps whose package source URL dies and cannot be repaired,
- re-check projects that were not packaged yet (so they appear later when they ship Channel metadata).

Read [awesome-webos SAFETY.md](https://github.com/tolgakurtuluss/awesome-webos/blob/main/SAFETY.md) before installing anything on your TV.

## Notes

This project is independent community tooling. It is not affiliated with LG Electronics or the webosbrew maintainers. Inclusion is not a security audit.
