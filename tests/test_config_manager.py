from __future__ import annotations

import json

import pytest

from config_manager import (
    DEFAULT_SETTINGS,
    ProfileError,
    create_profile,
    delete_profile,
    discover_profiles,
    load_profile,
    normalize_profile_filename,
    profile_path,
    save_profile,
    validate_profile,
)


def runtime_profile() -> dict[str, object]:
    return {
        **DEFAULT_SETTINGS,
        "user_lst": "alice, @bob",
        "cookie": "auth_token=test; ct0=csrf-token;",
    }


def test_profile_round_trip_and_discovery(tmp_path):
    saved = save_profile("settings.json", runtime_profile(), tmp_path)

    assert saved["user_lst"] == "alice,bob"
    assert load_profile("settings.json", tmp_path, require_runtime=True) == saved

    profiles = discover_profiles(tmp_path)
    assert profiles == [
        {
            "filename": "settings.json",
            "label": "默认配置",
            "users": ["alice", "bob"],
            "save_path": "",
            "modified_at": profiles[0]["modified_at"],
            "valid": True,
            "error": None,
        }
    ]


def test_create_clone_and_delete_profile(tmp_path):
    save_profile("settings.json", runtime_profile(), tmp_path)
    filename = create_profile("artists", clone_from="settings.json", root=tmp_path)

    assert filename == "settings-artists.json"
    assert load_profile(filename, tmp_path)["cookie"] == "auth_token=test; ct0=csrf-token;"

    delete_profile(filename, tmp_path)
    assert not (tmp_path / filename).exists()
    with pytest.raises(ProfileError, match="不能删除"):
        delete_profile("settings.json", tmp_path)


@pytest.mark.parametrize("name", ["../escape", "folder/settings.json", "settings?.json", ""])
def test_profile_filename_rejects_unsafe_names(name):
    with pytest.raises(ProfileError):
        normalize_profile_filename(name)


def test_profile_path_stays_inside_root(tmp_path):
    assert profile_path("personal", tmp_path) == tmp_path / "settings-personal.json"


def test_validation_rejects_conflicting_modes_and_invalid_runtime():
    conflicting = {**runtime_profile(), "has_retweet": True, "likes": True}
    with pytest.raises(ProfileError, match="只能选择一个"):
        validate_profile(conflicting)

    with pytest.raises(ProfileError, match="ct0"):
        validate_profile({**runtime_profile(), "cookie": "auth_token=only;"}, require_runtime=True)


def test_invalid_json_is_reported_by_discovery(tmp_path):
    (tmp_path / "settings-broken.json").write_text("{broken", encoding="utf-8")

    profile = discover_profiles(tmp_path)[0]
    assert profile["valid"] is False
    assert "JSON 格式错误" in profile["error"]


def test_save_preserves_legacy_metadata_keys(tmp_path):
    source = {**runtime_profile(), "user_lst_info": "legacy help text", "custom": {"keep": True}}
    save_profile("settings.json", source, tmp_path)

    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert raw["user_lst_info"] == "legacy help text"
    assert raw["custom"] == {"keep": True}
