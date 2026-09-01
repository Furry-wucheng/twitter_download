"""Configuration profile discovery, validation, and persistence."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent

DEFAULT_SETTINGS: dict[str, Any] = {
    "save_path": "",
    "user_lst": "",
    "cookie": "",
    "has_retweet": False,
    "high_lights": False,
    "likes": False,
    "time_range": "1990-01-01:2030-01-01",
    "down_log": True,
    "share_cache": False,
    "autoSync": False,
    "image_format": "orig",
    "has_video": True,
    "log_output": True,
    "max_concurrent_requests": 8,
    "proxy": "",
    "md_output": False,
    "media_count_limit": 350,
}

BOOLEAN_FIELDS = {
    "has_retweet",
    "high_lights",
    "likes",
    "down_log",
    "share_cache",
    "autoSync",
    "has_video",
    "log_output",
    "md_output",
}

_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_DATE_RANGE = re.compile(r"^(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})$")


class ProfileError(ValueError):
    """Raised when a profile is missing, invalid, or unsafe to access."""


@dataclass(frozen=True, slots=True)
class ProfileSummary:
    filename: str
    label: str
    users: list[str]
    save_path: str
    modified_at: str
    valid: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_profile_filename(name: str) -> str:
    """Turn a friendly profile name into a safe settings*.json filename."""
    value = name.strip()
    if not value:
        raise ProfileError("配置名称不能为空")
    if _INVALID_FILENAME.search(value) or value in {".", ".."}:
        raise ProfileError("配置名称包含无效字符")

    if not value.lower().endswith(".json"):
        value += ".json"
    if not value.lower().startswith("settings"):
        value = f"settings-{value}"
    if value.lower() == "settings-.json":
        raise ProfileError("配置名称不能为空")
    return value


def profile_path(filename: str, root: Path = PROJECT_ROOT) -> Path:
    """Resolve a profile path while preventing path traversal."""
    normalized = normalize_profile_filename(filename)
    resolved_root = root.resolve()
    resolved = (resolved_root / normalized).resolve()
    if resolved.parent != resolved_root:
        raise ProfileError("配置文件必须位于项目目录中")
    return resolved


def _profile_label(filename: str) -> str:
    stem = Path(filename).stem
    suffix = stem.removeprefix("settings").lstrip("-_")
    return suffix or "默认配置"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProfileError(f"找不到配置文件：{path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileError(f"JSON 格式错误（第 {exc.lineno} 行）：{exc.msg}") from exc
    except OSError as exc:
        raise ProfileError(f"无法读取配置文件：{exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("配置文件顶层必须是 JSON 对象")
    return data


def validate_profile(data: dict[str, Any], *, require_runtime: bool = False) -> dict[str, Any]:
    """Validate known fields while preserving legacy comment/metadata keys."""
    normalized = {**DEFAULT_SETTINGS, **data}

    for field in BOOLEAN_FIELDS:
        if not isinstance(normalized[field], bool):
            raise ProfileError(f"{field} 必须是 true 或 false")

    for field in ("save_path", "user_lst", "cookie", "time_range", "proxy", "image_format"):
        if not isinstance(normalized[field], str):
            raise ProfileError(f"{field} 必须是字符串")

    if normalized["image_format"] not in {"orig", "jpg", "png"}:
        raise ProfileError("image_format 只能是 orig、jpg 或 png")

    concurrency = normalized["max_concurrent_requests"]
    if isinstance(concurrency, bool) or not isinstance(concurrency, int) or not 1 <= concurrency <= 64:
        raise ProfileError("max_concurrent_requests 必须是 1 到 64 的整数")

    media_limit = normalized["media_count_limit"]
    if isinstance(media_limit, bool) or not isinstance(media_limit, int) or media_limit < 0:
        raise ProfileError("media_count_limit 必须是大于等于 0 的整数")

    selected_modes = sum(bool(normalized[key]) for key in ("has_retweet", "high_lights", "likes"))
    if selected_modes > 1:
        raise ProfileError("转推、亮点和喜欢模式只能选择一个")

    time_range = normalized["time_range"].strip()
    if time_range:
        match = _DATE_RANGE.fullmatch(time_range)
        if not match:
            raise ProfileError("time_range 格式应为 YYYY-MM-DD:YYYY-MM-DD")
        try:
            start = date.fromisoformat(match.group(1))
            end = date.fromisoformat(match.group(2))
        except ValueError as exc:
            raise ProfileError(f"time_range 包含无效日期：{exc}") from exc
        if start > end:
            raise ProfileError("time_range 的开始日期不能晚于结束日期")

    users = [user.strip().removeprefix("@") for user in normalized["user_lst"].split(",")]
    normalized["user_lst"] = ",".join(user for user in users if user)
    normalized["time_range"] = time_range
    normalized["save_path"] = normalized["save_path"].strip()
    normalized["proxy"] = normalized["proxy"].strip()

    if require_runtime:
        if not normalized["user_lst"]:
            raise ProfileError("请至少填写一个目标用户名")
        if not re.search(r"(?:^|;\s*)ct0=[^;]+", normalized["cookie"]):
            raise ProfileError("cookie 中缺少有效的 ct0 字段")

    return normalized


def load_profile(
    filename: str,
    root: Path = PROJECT_ROOT,
    *,
    require_runtime: bool = False,
) -> dict[str, Any]:
    path = profile_path(filename, root)
    return validate_profile(_read_json(path), require_runtime=require_runtime)


def save_profile(filename: str, data: dict[str, Any], root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Atomically save a validated profile."""
    path = profile_path(filename, root)
    normalized = validate_profile(data)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(normalized, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise ProfileError(f"无法保存配置文件：{exc}") from exc
    return normalized


def create_profile(
    name: str,
    *,
    clone_from: str | None = None,
    root: Path = PROJECT_ROOT,
) -> str:
    filename = normalize_profile_filename(name)
    target = profile_path(filename, root)
    if target.exists():
        raise ProfileError(f"配置文件已存在：{filename}")
    data = load_profile(clone_from, root) if clone_from else DEFAULT_SETTINGS.copy()
    save_profile(filename, data, root)
    return filename


def delete_profile(filename: str, root: Path = PROJECT_ROOT) -> None:
    path = profile_path(filename, root)
    if path.name.lower() == "settings.json":
        raise ProfileError("默认配置 settings.json 不能删除")
    try:
        path.unlink()
    except FileNotFoundError as exc:
        raise ProfileError(f"找不到配置文件：{path.name}") from exc
    except OSError as exc:
        raise ProfileError(f"无法删除配置文件：{exc}") from exc


def discover_profiles(root: Path = PROJECT_ROOT) -> list[dict[str, Any]]:
    profiles: list[ProfileSummary] = []
    for path in sorted(root.glob("settings*.json"), key=lambda item: item.name.casefold()):
        if not path.is_file():
            continue
        try:
            data = load_profile(path.name, root)
            users = [user for user in data["user_lst"].split(",") if user]
            summary = ProfileSummary(
                filename=path.name,
                label=_profile_label(path.name),
                users=users,
                save_path=data["save_path"],
                modified_at=datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                valid=True,
            )
        except (OSError, ProfileError) as exc:
            summary = ProfileSummary(
                filename=path.name,
                label=_profile_label(path.name),
                users=[],
                save_path="",
                modified_at="",
                valid=False,
                error=str(exc),
            )
        profiles.append(summary)
    return [profile.to_dict() for profile in profiles]
