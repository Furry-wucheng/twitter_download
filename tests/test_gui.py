from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from config_manager import DEFAULT_SETTINGS
from gui import ConfigEditor, PathLabel
from gui_style import build_stylesheet


@pytest.fixture(scope="module")
def application():
    app = QApplication.instance() or QApplication([])
    yield app


def test_config_editor_round_trip(application):
    editor = ConfigEditor()
    config = {
        **DEFAULT_SETTINGS,
        "user_lst": "alice,bob",
        "cookie": "auth_token=test; ct0=csrf;",
        "save_path": "D:/archive",
        "has_retweet": True,
        "image_format": "jpg",
        "max_concurrent_requests": 12,
        "custom_metadata": "preserved",
    }

    editor.load("settings-team.json", config)
    collected = editor.collect()

    assert collected["user_lst"] == "alice,bob"
    assert collected["has_retweet"] is True
    assert collected["high_lights"] is False
    assert collected["image_format"] == "jpg"
    assert collected["max_concurrent_requests"] == 12
    assert collected["custom_metadata"] == "preserved"
    editor.deleteLater()


def test_filename_display_labels():
    assert PathLabel.from_filename("settings.json") == "默认配置"
    assert PathLabel.from_filename("settings-artists.json") == "artists"
    assert PathLabel.from_filename("settings_team.json") == "team"


def test_likes_mode_keeps_publication_dates_enabled(application):
    editor = ConfigEditor()
    editor.load("settings-likes.json", {**DEFAULT_SETTINGS, "likes": True})

    assert editor.start_date.isEnabled()
    assert editor.end_date.isEnabled()
    assert "推文发布日期" in editor.start_date.toolTip()
    editor.deleteLater()


def test_stylesheet_contains_the_control_desk_tokens():
    stylesheet = build_stylesheet()
    assert "#e9a23b" in stylesheet
    assert "QPlainTextEdit#console" in stylesheet
