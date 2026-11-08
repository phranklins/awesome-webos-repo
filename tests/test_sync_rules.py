"""Lightweight checks for sync notice/title rules (no network)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sync_awesome_webos import apply_notice_fields, notice_from_description  # noqa: E402


def test_youtube_collision_notice():
    label, notice = notice_from_description("anything", "youtube.leanback.v4")
    assert label == "needs_notice"
    assert notice == "youtube_collision"


def test_root_notice():
    label, notice = notice_from_description("Requires root and the Homebrew Channel.", "com.example.app")
    assert label == "needs_notice"
    assert notice and "root" in notice.lower()


def test_preserve_explicit_title_field():
    entry = {
        "name": "YouTube Foxtended",
        "id": "youtube.leanback.v4",
        "title": "YouTube Foxtended",
        "label": "packaged",
    }
    apply_notice_fields(entry, "needs_notice", "youtube_collision")
    assert entry["title"] == "YouTube Foxtended"
    assert entry["notice"] == "youtube_collision"
    assert entry["label"] == "needs_notice"


if __name__ == "__main__":
    test_youtube_collision_notice()
    test_root_notice()
    test_preserve_explicit_title_field()
    print("ok")
