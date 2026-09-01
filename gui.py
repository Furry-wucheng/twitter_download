"""PySide6 desktop control desk for Twitter Download."""

from __future__ import annotations

import argparse
import codecs
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from PySide6.QtCore import QDate, QProcess, QProcessEnvironment, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStatusBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config_manager import (
    PROJECT_ROOT,
    ProfileError,
    create_profile,
    delete_profile,
    discover_profiles,
    load_profile,
    profile_path,
    save_profile,
)
from gui_style import build_stylesheet

ACTIVE_STATES = {"starting", "running", "stopping"}
STATUS_LABELS = {
    "idle": "IDLE",
    "starting": "STARTING",
    "running": "RUNNING",
    "stopping": "STOPPING",
    "stopped": "STOPPED",
    "completed": "DONE",
    "failed": "FAILED",
}


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def now_label() -> str:
    return datetime.now().astimezone().strftime("%H:%M:%S")


@dataclass(slots=True)
class JobState:
    profile: str
    process: QProcess
    status: str = "starting"
    started_at: str = field(default_factory=now_label)
    finished_at: str = ""
    return_code: int | None = None
    stop_requested: bool = False
    decoder: Any = field(default_factory=lambda: codecs.getincrementaldecoder("utf-8")(errors="replace"))
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=1200))


class DownloadJobManager(QWidget):
    """Own and observe QProcess instances without blocking the GUI thread."""

    job_updated = Signal(str, str)
    log_received = Signal(str, str)
    error_raised = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._jobs: dict[str, JobState] = {}

    def start(self, filename: str) -> None:
        safe_name = profile_path(filename).name
        load_profile(safe_name, require_runtime=True)
        current = self._jobs.get(safe_name)
        if current and current.process.state() != QProcess.ProcessState.NotRunning:
            raise ProfileError(f"{safe_name} 已经在运行")

        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments(["-u", str(PROJECT_ROOT / "main.py"), "--config", safe_name])
        process.setWorkingDirectory(str(PROJECT_ROOT))
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        environment = QProcessEnvironment.systemEnvironment()
        environment.insert("PYTHONIOENCODING", "utf-8")
        environment.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(environment)

        job = JobState(profile=safe_name, process=process)
        self._jobs[safe_name] = job
        process.started.connect(lambda name=safe_name: self._on_started(name))
        process.readyReadStandardOutput.connect(lambda name=safe_name: self._read_output(name))
        process.errorOccurred.connect(lambda error, name=safe_name: self._on_error(name, error))
        process.finished.connect(
            lambda exit_code, exit_status, name=safe_name: self._on_finished(name, exit_code, exit_status)
        )

        self._append(job, f"[{now_label()}] 启动配置 {safe_name}\n")
        self.job_updated.emit(safe_name, job.status)
        process.start()

    def stop(self, filename: str) -> None:
        safe_name = profile_path(filename).name
        job = self._jobs.get(safe_name)
        if not job or job.process.state() == QProcess.ProcessState.NotRunning:
            raise ProfileError(f"{safe_name} 当前没有运行中的任务")
        job.stop_requested = True
        job.status = "stopping"
        self._append(job, f"\n[{now_label()}] 正在停止任务…\n")
        self.job_updated.emit(safe_name, job.status)
        job.process.terminate()
        QTimer.singleShot(3000, lambda name=safe_name: self._force_stop(name))

    def _force_stop(self, filename: str) -> None:
        job = self._jobs.get(filename)
        if job and job.process.state() != QProcess.ProcessState.NotRunning:
            job.process.kill()

    def _on_started(self, filename: str) -> None:
        job = self._jobs.get(filename)
        if not job:
            return
        job.status = "running"
        self._append(job, f"[{now_label()}] 进程已就绪，PID {job.process.processId()}\n")
        self.job_updated.emit(filename, job.status)

    def _read_output(self, filename: str) -> None:
        job = self._jobs.get(filename)
        if not job:
            return
        payload = bytes(job.process.readAllStandardOutput())
        if payload:
            self._append(job, job.decoder.decode(payload))

    def _on_error(self, filename: str, error: QProcess.ProcessError) -> None:
        job = self._jobs.get(filename)
        if not job:
            return
        if error == QProcess.ProcessError.FailedToStart:
            job.status = "failed"
            message = f"无法启动下载进程：{job.process.errorString()}"
            self._append(job, f"[{now_label()}] {message}\n")
            self.error_raised.emit(message)
            self.job_updated.emit(filename, job.status)

    def _on_finished(
        self,
        filename: str,
        exit_code: int,
        _: QProcess.ExitStatus,
    ) -> None:
        job = self._jobs.get(filename)
        if not job:
            return
        trailing = job.decoder.decode(b"", final=True)
        if trailing:
            self._append(job, trailing)
        job.return_code = exit_code
        job.finished_at = now_label()
        if job.stop_requested:
            job.status = "stopped"
        else:
            job.status = "completed" if exit_code == 0 else "failed"
        self._append(job, f"\n[{now_label()}] 任务结束，退出码 {exit_code}\n")
        self.job_updated.emit(filename, job.status)

    def _append(self, job: JobState, text: str) -> None:
        if not text:
            return
        job.logs.append(text)
        self.log_received.emit(job.profile, text)

    def status_for(self, filename: str) -> str:
        job = self._jobs.get(filename)
        return job.status if job else "idle"

    def is_active(self, filename: str) -> bool:
        return self.status_for(filename) in ACTIVE_STATES

    def jobs(self) -> list[JobState]:
        return sorted(self._jobs.values(), key=lambda job: job.started_at, reverse=True)

    def logs_for(self, filename: str) -> str:
        job = self._jobs.get(filename)
        return "".join(job.logs) if job else ""

    def active_count(self) -> int:
        return sum(job.status in ACTIVE_STATES for job in self._jobs.values())

    def shutdown(self) -> None:
        active_jobs = [job for job in self._jobs.values() if job.process.state() != QProcess.ProcessState.NotRunning]
        for job in active_jobs:
            job.stop_requested = True
            job.process.terminate()
        for job in active_jobs:
            if not job.process.waitForFinished(1500):
                job.process.kill()
                job.process.waitForFinished(500)


class ProfileItemWidget(QFrame):
    def __init__(self, profile: dict[str, Any], status: str) -> None:
        super().__init__()
        self.setObjectName("profileItem")
        self.setProperty("selected", False)
        self.setMinimumHeight(76)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 10, 9)
        layout.setSpacing(4)

        top = QHBoxLayout()
        name = QLabel(profile["label"])
        name.setObjectName("profileName")
        pill = QLabel()
        pill.setObjectName("statusPill")
        top.addWidget(name, 1)
        top.addWidget(pill)
        layout.addLayout(top)

        users = ", ".join(f"@{user}" for user in profile["users"][:2]) or "未设置目标用户"
        if len(profile["users"]) > 2:
            users += f" +{len(profile['users']) - 2}"
        meta = QLabel(users)
        meta.setObjectName("profileMeta")
        meta.setToolTip(profile["filename"])
        layout.addWidget(meta)

        self.status_pill = pill
        self.set_status(status if profile["valid"] else "failed")

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        repolish(self)

    def set_status(self, status: str) -> None:
        self.status_pill.setText(STATUS_LABELS.get(status, status.upper()))
        self.status_pill.setProperty("status", status)
        repolish(self.status_pill)


class ProfileRail(QFrame):
    selected = Signal(str)
    create_requested = Signal()
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("darkPanel")
        self.setMinimumWidth(245)
        self.setMaximumWidth(285)
        self._widgets: dict[str, ProfileItemWidget] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        kicker = QLabel("01 / PROFILES")
        kicker.setObjectName("panelKicker")
        title = QLabel("配置档案")
        title.setObjectName("panelTitle")
        title_box.addWidget(kicker)
        title_box.addWidget(title)
        heading.addLayout(title_box, 1)
        new_button = QToolButton()
        new_button.setText("+")
        new_button.setToolTip("新建配置")
        new_button.clicked.connect(self.create_requested)
        heading.addWidget(new_button)
        layout.addLayout(heading)

        self.count_label = QLabel("0 个可用档案")
        self.count_label.setObjectName("muted")
        layout.addWidget(self.count_label)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("profileList")
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.currentItemChanged.connect(self._on_current_changed)
        layout.addWidget(self.list_widget, 1)

        footer = QHBoxLayout()
        footer_label = QLabel("每个配置可独立运行")
        footer_label.setObjectName("headerMeta")
        refresh_button = QToolButton()
        refresh_button.setText("↻")
        refresh_button.setToolTip("重新扫描配置")
        refresh_button.clicked.connect(self.refresh_requested)
        footer.addWidget(footer_label, 1)
        footer.addWidget(refresh_button)
        layout.addLayout(footer)

    def set_profiles(self, profiles: list[dict[str, Any]], statuses: dict[str, str], selected: str | None) -> None:
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        self._widgets.clear()
        target_item: QListWidgetItem | None = None
        for profile in profiles:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, profile["filename"])
            item.setSizeHint(QSize(220, 82))
            widget = ProfileItemWidget(profile, statuses.get(profile["filename"], "idle"))
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)
            self._widgets[profile["filename"]] = widget
            if profile["filename"] == selected:
                target_item = item
        self.count_label.setText(f"{len(profiles)} 个可用档案")
        self.list_widget.blockSignals(False)
        if target_item:
            self.list_widget.setCurrentItem(target_item)
        elif self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _on_current_changed(self, current: QListWidgetItem | None, _: QListWidgetItem | None) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            widget = self.list_widget.itemWidget(item)
            if isinstance(widget, ProfileItemWidget):
                widget.set_selected(item is current)
        if current:
            self.selected.emit(current.data(Qt.ItemDataRole.UserRole))

    def select_filename(self, filename: str) -> None:
        for row in range(self.list_widget.count()):
            item = self.list_widget.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == filename:
                self.list_widget.setCurrentItem(item)
                return

    def update_status(self, filename: str, status: str) -> None:
        widget = self._widgets.get(filename)
        if widget:
            widget.set_status(status)


class SectionCard(QFrame):
    def __init__(self, title: str, code: str) -> None:
        super().__init__()
        self.setObjectName("sectionCard")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(16, 14, 16, 16)
        self.body.setSpacing(12)
        heading = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        code_label = QLabel(code)
        code_label.setObjectName("sectionCode")
        heading.addWidget(title_label)
        heading.addStretch()
        heading.addWidget(code_label)
        self.body.addLayout(heading)


def field_label(text: str, hint: str = "") -> QWidget:
    box = QWidget()
    layout = QHBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    layout.addWidget(label)
    if hint:
        helper = QLabel(hint)
        helper.setObjectName("fieldHint")
        layout.addWidget(helper)
    layout.addStretch()
    return box


class ConfigEditor(QFrame):
    save_requested = Signal()
    duplicate_requested = Signal()
    delete_requested = Signal()
    dirty_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("paperPanel")
        self._filename: str | None = None
        self._config: dict[str, Any] = {}
        self._loading = False
        self.dirty = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 10, 12)
        outer.setSpacing(12)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        kicker = QLabel("02 / PARAMETERS")
        kicker.setObjectName("panelKicker")
        self.title = QLabel("选择一个配置")
        self.title.setObjectName("panelTitle")
        self.subtitle = QLabel("目标、输出和下载策略会保存在独立 JSON 档案中。")
        self.subtitle.setObjectName("muted")
        title_box.addWidget(kicker)
        title_box.addWidget(self.title)
        title_box.addWidget(self.subtitle)
        heading.addLayout(title_box, 1)

        self.dirty_label = QLabel("未保存")
        self.dirty_label.setStyleSheet("color: #9b5d08; font-weight: 700;")
        self.dirty_label.hide()
        heading.addWidget(self.dirty_label)
        duplicate_button = QPushButton("复制")
        duplicate_button.clicked.connect(self.duplicate_requested)
        self.delete_button = QPushButton("删除")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.clicked.connect(self.delete_requested)
        self.save_button = QPushButton("保存配置")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self.save_requested)
        heading.addWidget(duplicate_button)
        heading.addWidget(self.delete_button)
        heading.addWidget(self.save_button)
        outer.addLayout(heading)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("editorScroll")
        self.scroll.setWidgetResizable(True)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 4)
        content_layout.setSpacing(10)
        self.scroll.setWidget(content)
        outer.addWidget(self.scroll, 1)

        target = SectionCard("目标", "TARGET")
        target_grid = QGridLayout()
        target_grid.setHorizontalSpacing(12)
        target_grid.setVerticalSpacing(8)
        self.users = QLineEdit()
        self.users.setPlaceholderText("lilmonix3, matchach")
        target_grid.addWidget(field_label("用户名", "逗号分隔，可填写多个"), 0, 0, 1, 2)
        target_grid.addWidget(self.users, 1, 0, 1, 2)
        self.cookie = QLineEdit()
        self.cookie.setEchoMode(QLineEdit.EchoMode.Password)
        self.cookie.setPlaceholderText("auth_token=…; ct0=…;")
        reveal = QToolButton()
        reveal.setText("◉")
        reveal.setToolTip("显示或隐藏 Cookie")
        reveal.setCheckable(True)
        reveal.toggled.connect(
            lambda shown: self.cookie.setEchoMode(
                QLineEdit.EchoMode.Normal if shown else QLineEdit.EchoMode.Password
            )
        )
        cookie_row = QHBoxLayout()
        cookie_row.addWidget(self.cookie, 1)
        cookie_row.addWidget(reveal)
        target_grid.addWidget(field_label("Cookie", "至少包含 auth_token 与 ct0"), 2, 0, 1, 2)
        target_grid.addLayout(cookie_row, 3, 0, 1, 2)
        target.body.addLayout(target_grid)
        content_layout.addWidget(target)

        mode_card = SectionCard("抓取模式", "SOURCE MODE")
        mode_grid = QGridLayout()
        mode_grid.setHorizontalSpacing(14)
        mode_grid.setVerticalSpacing(8)
        self.mode_group = QButtonGroup(self)
        self.mode_buttons: dict[str, QRadioButton] = {}
        for index, (key, label) in enumerate(
            (("media", "媒体"), ("retweet", "含转推"), ("highlights", "亮点"), ("likes", "喜欢"))
        ):
            button = QRadioButton(label)
            self.mode_group.addButton(button)
            self.mode_buttons[key] = button
            mode_grid.addWidget(button, 0, index)
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        mode_grid.addWidget(field_label("开始日期", "Likes 按推文发布日期筛选"), 1, 0, 1, 2)
        mode_grid.addWidget(field_label("结束日期"), 1, 2, 1, 2)
        mode_grid.addWidget(self.start_date, 2, 0, 1, 2)
        mode_grid.addWidget(self.end_date, 2, 2, 1, 2)
        mode_card.body.addLayout(mode_grid)
        content_layout.addWidget(mode_card)

        output = SectionCard("媒体与输出", "MEDIA / OUTPUT")
        output_grid = QGridLayout()
        output_grid.setHorizontalSpacing(12)
        output_grid.setVerticalSpacing(8)
        self.save_path = QLineEdit()
        self.save_path.setPlaceholderText("留空则使用项目目录")
        browse = QToolButton()
        browse.setText("…")
        browse.setToolTip("选择输出目录")
        browse.clicked.connect(self._choose_directory)
        path_row = QHBoxLayout()
        path_row.addWidget(self.save_path, 1)
        path_row.addWidget(browse)
        output_grid.addWidget(field_label("保存目录"), 0, 0, 1, 2)
        output_grid.addLayout(path_row, 1, 0, 1, 2)
        self.image_format = QComboBox()
        self.image_format.addItem("跟随原图", "orig")
        self.image_format.addItem("统一 JPG", "jpg")
        self.image_format.addItem("统一 PNG", "png")
        self.media_limit = QSpinBox()
        self.media_limit.setRange(0, 100_000)
        self.media_limit.setSpecialValueText("不限制")
        output_grid.addWidget(field_label("图片格式"), 2, 0)
        output_grid.addWidget(field_label("单份 Markdown 媒体上限"), 2, 1)
        output_grid.addWidget(self.image_format, 3, 0)
        output_grid.addWidget(self.media_limit, 3, 1)

        toggles = QGridLayout()
        toggles.setHorizontalSpacing(18)
        toggle_specs = (
            ("has_video", "下载视频"),
            ("md_output", "生成 Markdown"),
            ("down_log", "启用下载缓存"),
            ("share_cache", "多用户共享缓存"),
            ("autoSync", "自动同步增量"),
            ("log_output", "详细下载日志"),
        )
        self.toggles: dict[str, QCheckBox] = {}
        for index, (key, label) in enumerate(toggle_specs):
            checkbox = QCheckBox(label)
            self.toggles[key] = checkbox
            toggles.addWidget(checkbox, index // 3, index % 3)
        output_grid.addLayout(toggles, 4, 0, 1, 2)
        output.body.addLayout(output_grid)
        content_layout.addWidget(output)

        network = SectionCard("网络", "NETWORK")
        network_grid = QGridLayout()
        network_grid.setHorizontalSpacing(12)
        network_grid.setVerticalSpacing(8)
        self.proxy = QLineEdit()
        self.proxy.setPlaceholderText("http://127.0.0.1:7890")
        network_grid.addWidget(field_label("代理地址", "可选"), 0, 0, 1, 2)
        network_grid.addWidget(self.proxy, 1, 0, 1, 2)
        self.concurrency_slider = QSlider(Qt.Orientation.Horizontal)
        self.concurrency_slider.setRange(1, 64)
        self.concurrency = QSpinBox()
        self.concurrency.setRange(1, 64)
        self.concurrency_slider.valueChanged.connect(self.concurrency.setValue)
        self.concurrency.valueChanged.connect(self.concurrency_slider.setValue)
        network_grid.addWidget(field_label("并发请求", "1 谨慎 / 64 快速"), 2, 0, 1, 2)
        network_grid.addWidget(self.concurrency_slider, 3, 0)
        network_grid.addWidget(self.concurrency, 3, 1)
        network_grid.setColumnStretch(0, 1)
        network.body.addLayout(network_grid)
        content_layout.addWidget(network)
        content_layout.addStretch()

        self._connect_change_signals()
        self.set_enabled(False)

    @property
    def filename(self) -> str | None:
        return self._filename

    def _connect_change_signals(self) -> None:
        for line_edit in (self.users, self.cookie, self.save_path, self.proxy):
            line_edit.textChanged.connect(self._mark_dirty)
        for date_edit in (self.start_date, self.end_date):
            date_edit.dateChanged.connect(self._mark_dirty)
        self.image_format.currentIndexChanged.connect(self._mark_dirty)
        self.media_limit.valueChanged.connect(self._mark_dirty)
        self.concurrency.valueChanged.connect(self._mark_dirty)
        for button in self.mode_buttons.values():
            button.toggled.connect(self._mode_changed)
        for checkbox in self.toggles.values():
            checkbox.toggled.connect(self._mark_dirty)

    def _mode_changed(self) -> None:
        likes_mode = self.mode_buttons["likes"].isChecked()
        tooltip = "Likes 模式按原推文发布日期筛选，不是点赞日期" if likes_mode else ""
        self.start_date.setToolTip(tooltip)
        self.end_date.setToolTip(tooltip)
        self._mark_dirty()

    def _mark_dirty(self, *_: object) -> None:
        if self._loading or not self._filename:
            return
        self.dirty = True
        self.dirty_label.show()
        self.dirty_changed.emit(True)

    def set_enabled(self, enabled: bool) -> None:
        self.scroll.setEnabled(enabled)
        self.save_button.setEnabled(enabled)
        self.delete_button.setEnabled(enabled and self._filename != "settings.json")

    def load(self, filename: str, config: dict[str, Any]) -> None:
        self._loading = True
        self._filename = filename
        self._config = config.copy()
        self.title.setText(PathLabel.from_filename(filename))
        self.subtitle.setText(filename)
        self.users.setText(config["user_lst"])
        self.cookie.setText(config["cookie"])
        self.save_path.setText(config["save_path"])
        self.proxy.setText(config["proxy"])
        image_index = self.image_format.findData(config["image_format"])
        self.image_format.setCurrentIndex(max(image_index, 0))
        self.media_limit.setValue(config["media_count_limit"])
        self.concurrency.setValue(config["max_concurrent_requests"])
        for key, checkbox in self.toggles.items():
            checkbox.setChecked(bool(config[key]))

        mode = "media"
        if config["has_retweet"]:
            mode = "retweet"
        elif config["high_lights"]:
            mode = "highlights"
        elif config["likes"]:
            mode = "likes"
        self.mode_buttons[mode].setChecked(True)

        time_range = config["time_range"] or "1990-01-01:2030-01-01"
        start_text, end_text = time_range.split(":", 1)
        self.start_date.setDate(QDate.fromString(start_text, "yyyy-MM-dd"))
        self.end_date.setDate(QDate.fromString(end_text, "yyyy-MM-dd"))
        self.start_date.setEnabled(True)
        self.end_date.setEnabled(True)
        self._loading = False
        self.mark_saved()
        self.set_enabled(True)

    def collect(self) -> dict[str, Any]:
        data = self._config.copy()
        data.update(
            {
                "user_lst": self.users.text(),
                "cookie": self.cookie.text(),
                "save_path": self.save_path.text(),
                "proxy": self.proxy.text(),
                "time_range": (
                    f"{self.start_date.date().toString('yyyy-MM-dd')}:"
                    f"{self.end_date.date().toString('yyyy-MM-dd')}"
                ),
                "image_format": self.image_format.currentData(),
                "media_count_limit": self.media_limit.value(),
                "max_concurrent_requests": self.concurrency.value(),
                "has_retweet": self.mode_buttons["retweet"].isChecked(),
                "high_lights": self.mode_buttons["highlights"].isChecked(),
                "likes": self.mode_buttons["likes"].isChecked(),
            }
        )
        for key, checkbox in self.toggles.items():
            data[key] = checkbox.isChecked()
        return data

    def mark_saved(self) -> None:
        self.dirty = False
        self.dirty_label.hide()
        self.dirty_changed.emit(False)

    def _choose_directory(self) -> None:
        start = self.save_path.text() or str(PROJECT_ROOT)
        selected = QFileDialog.getExistingDirectory(self, "选择媒体保存目录", start)
        if selected:
            self.save_path.setText(selected)


class PathLabel:
    @staticmethod
    def from_filename(filename: str) -> str:
        stem = filename.removesuffix(".json")
        label = stem.removeprefix("settings").lstrip("-_")
        return label or "默认配置"


class OperationsPanel(QFrame):
    start_stop_requested = Signal()
    profile_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("darkPanel")
        self.setMinimumWidth(340)
        self.setMaximumWidth(420)
        self._selected: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 14)
        layout.setSpacing(12)

        heading = QHBoxLayout()
        title_box = QVBoxLayout()
        kicker = QLabel("03 / OPERATIONS")
        kicker.setObjectName("panelKicker")
        title = QLabel("任务信号")
        title.setObjectName("panelTitle")
        title_box.addWidget(kicker)
        title_box.addWidget(title)
        heading.addLayout(title_box, 1)
        self.active_label = QLabel("0 ACTIVE")
        self.active_label.setObjectName("headerMeta")
        heading.addWidget(self.active_label)
        layout.addLayout(heading)

        launch = QFrame()
        launch.setObjectName("launchCard")
        launch_layout = QVBoxLayout(launch)
        launch_layout.setContentsMargins(13, 11, 13, 13)
        launch_label = QLabel("READY PROFILE")
        launch_label.setObjectName("headerMeta")
        self.launch_name = QLabel("尚未选择")
        self.launch_name.setObjectName("launchName")
        self.run_button = QPushButton("开始下载  ↗")
        self.run_button.setObjectName("runButton")
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self.start_stop_requested)
        launch_layout.addWidget(launch_label)
        launch_layout.addWidget(self.launch_name)
        launch_layout.addWidget(self.run_button)
        layout.addWidget(launch)

        jobs_label = QLabel("TASK QUEUE")
        jobs_label.setObjectName("panelKicker")
        layout.addWidget(jobs_label)
        self.job_list = QListWidget()
        self.job_list.setObjectName("jobList")
        self.job_list.setMaximumHeight(170)
        self.job_list.itemClicked.connect(
            lambda item: self.profile_requested.emit(item.data(Qt.ItemDataRole.UserRole))
        )
        layout.addWidget(self.job_list)

        console_heading = QHBoxLayout()
        console_label = QLabel("LIVE OUTPUT")
        console_label.setObjectName("panelKicker")
        clear_button = QPushButton("清空视图")
        clear_button.setMaximumWidth(90)
        clear_button.clicked.connect(self.clear_console)
        console_heading.addWidget(console_label)
        console_heading.addStretch()
        console_heading.addWidget(clear_button)
        layout.addLayout(console_heading)
        self.console = QPlainTextEdit()
        self.console.setObjectName("console")
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(2500)
        self.console.setPlaceholderText("等待任务信号…")
        layout.addWidget(self.console, 1)

    def set_selected(self, filename: str, manager: DownloadJobManager) -> None:
        self._selected = filename
        self.launch_name.setText(PathLabel.from_filename(filename))
        self.run_button.setEnabled(True)
        self.console.setPlainText(manager.logs_for(filename))
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.refresh(manager)

    def refresh(self, manager: DownloadJobManager) -> None:
        self.active_label.setText(f"{manager.active_count()} ACTIVE")
        selected_row = -1
        self.job_list.clear()
        for index, job in enumerate(manager.jobs()):
            label = STATUS_LABELS.get(job.status, job.status.upper())
            item = QListWidgetItem(f"{label:<9}  {PathLabel.from_filename(job.profile)}\n{job.started_at}")
            item.setData(Qt.ItemDataRole.UserRole, job.profile)
            item.setToolTip(job.profile)
            self.job_list.addItem(item)
            if job.profile == self._selected:
                selected_row = index
        if selected_row >= 0:
            self.job_list.setCurrentRow(selected_row)

        if self._selected:
            running = manager.is_active(self._selected)
            self.run_button.setProperty("running", running)
            self.run_button.setText("停止任务  ■" if running else "开始下载  ↗")
            repolish(self.run_button)

    def append_log(self, filename: str, text: str) -> None:
        if filename != self._selected:
            return
        self.console.moveCursor(QTextCursor.MoveOperation.End)
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.MoveOperation.End)

    def clear_console(self) -> None:
        self.console.clear()


class ProfileDialog(QDialog):
    def __init__(
        self,
        profiles: list[dict[str, Any]],
        *,
        clone_from: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("新建配置档案")
        self.setMinimumWidth(430)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        kicker = QLabel("NEW / PROFILE")
        kicker.setObjectName("panelKicker")
        title = QLabel("建立一份配置档案")
        title.setObjectName("dialogTitle")
        description = QLabel("可以从空白开始，或复制已有配置后再调整。")
        description.setObjectName("muted")
        layout.addWidget(kicker)
        layout.addWidget(title)
        layout.addWidget(description)

        layout.addWidget(field_label("档案名称"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("illustrators")
        layout.addWidget(self.name_input)
        layout.addWidget(field_label("起始模板"))
        self.clone_combo = QComboBox()
        self.clone_combo.addItem("空白配置", None)
        for profile in profiles:
            self.clone_combo.addItem(profile["label"], profile["filename"])
        if clone_from:
            index = self.clone_combo.findData(clone_from)
            self.clone_combo.setCurrentIndex(max(index, 0))
            self.name_input.setText(f"{PathLabel.from_filename(clone_from)}-copy")
            self.name_input.selectAll()
        layout.addWidget(self.clone_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("建立档案")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name_input.setFocus()

    def _accept_if_valid(self) -> None:
        if not self.name_input.text().strip():
            self.name_input.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, str | None]:
        return self.name_input.text().strip(), self.clone_combo.currentData()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Archive Signal Desk — Twitter Download")
        self.resize(1500, 900)
        self.setMinimumSize(1180, 760)
        self._profiles: list[dict[str, Any]] = []
        self._selected: str | None = None

        root = QWidget()
        root.setObjectName("appRoot")
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 14, 16, 10)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_header())
        workspace = QHBoxLayout()
        workspace.setSpacing(12)
        self.rail = ProfileRail()
        self.editor = ConfigEditor()
        self.operations = OperationsPanel()
        workspace.addWidget(self.rail)
        workspace.addWidget(self.editor, 1)
        workspace.addWidget(self.operations)
        root_layout.addLayout(workspace, 1)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("本地控制台已就绪")

        self.jobs = DownloadJobManager(self)
        self.jobs.job_updated.connect(self._on_job_updated)
        self.jobs.log_received.connect(self.operations.append_log)
        self.jobs.error_raised.connect(self._show_error)
        self.rail.selected.connect(self.select_profile)
        self.rail.create_requested.connect(lambda: self.create_profile_dialog(False))
        self.rail.refresh_requested.connect(self.refresh_profiles)
        self.editor.save_requested.connect(self.save_selected)
        self.editor.duplicate_requested.connect(lambda: self.create_profile_dialog(True))
        self.editor.delete_requested.connect(self.delete_selected)
        self.operations.start_stop_requested.connect(self.start_or_stop)
        self.operations.profile_requested.connect(self.select_profile)

        save_action = QAction("保存配置", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_selected)
        self.addAction(save_action)

        self.refresh_profiles()

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("masthead")
        header.setFixedHeight(70)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(14, 9, 18, 9)

        mark = QLabel("TD")
        mark.setObjectName("brandMark")
        mark.setFixedSize(46, 46)
        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("ARCHIVE SIGNAL DESK")
        title.setObjectName("brandTitle")
        subtitle = QLabel("TWITTER DOWNLOAD / LOCAL MEDIA OPERATIONS")
        subtitle.setObjectName("brandSubtitle")
        brand.addWidget(title)
        brand.addWidget(subtitle)
        layout.addWidget(mark)
        layout.addSpacing(10)
        layout.addLayout(brand)
        layout.addStretch()
        meta = QLabel("LOCAL / 127.0.0.1   •   UV ENVIRONMENT")
        meta.setObjectName("headerMeta")
        self.clock = QLabel()
        self.clock.setObjectName("clock")
        layout.addWidget(meta)
        layout.addSpacing(18)
        layout.addWidget(self.clock)
        timer = QTimer(self)
        timer.timeout.connect(lambda: self.clock.setText(datetime.now().strftime("%H:%M:%S")))
        timer.start(1000)
        self.clock.setText(datetime.now().strftime("%H:%M:%S"))
        return header

    def refresh_profiles(self, select: str | None = None) -> None:
        self._profiles = discover_profiles()
        target = select or self._selected
        statuses = {profile["filename"]: self.jobs.status_for(profile["filename"]) for profile in self._profiles}
        self.rail.set_profiles(self._profiles, statuses, target)
        if not self._profiles:
            self.editor.set_enabled(False)
            self._selected = None

    def select_profile(self, filename: str) -> None:
        if self.editor.dirty and self._selected and filename != self._selected:
            answer = QMessageBox.question(
                self,
                "存在未保存修改",
                "当前配置有未保存修改。要先保存再切换吗？",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                self.rail.select_filename(self._selected)
                return
            if answer == QMessageBox.StandardButton.Save and not self.save_selected():
                self.rail.select_filename(self._selected)
                return
        try:
            config = load_profile(filename)
        except ProfileError as exc:
            self._show_error(str(exc))
            return
        self._selected = filename
        self.rail.select_filename(filename)
        self.editor.load(filename, config)
        self.editor.set_enabled(not self.jobs.is_active(filename))
        self.operations.set_selected(filename, self.jobs)
        self.statusBar().showMessage(f"已载入 {filename}", 3000)

    def save_selected(self) -> bool:
        if not self._selected:
            return False
        if self.jobs.is_active(self._selected):
            self._show_error("任务运行期间不能修改该配置")
            return False
        try:
            saved = save_profile(self._selected, self.editor.collect())
        except ProfileError as exc:
            self._show_error(str(exc))
            return False
        self.editor.load(self._selected, saved)
        self.editor.mark_saved()
        self.refresh_profiles(self._selected)
        self.statusBar().showMessage(f"已保存 {self._selected}", 4000)
        return True

    def create_profile_dialog(self, duplicate: bool) -> None:
        clone_from = self._selected if duplicate else None
        dialog = ProfileDialog(self._profiles, clone_from=clone_from, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        name, source = dialog.values()
        try:
            filename = create_profile(name, clone_from=source)
        except ProfileError as exc:
            self._show_error(str(exc))
            return
        self.refresh_profiles(filename)
        self.statusBar().showMessage(f"已建立 {filename}", 4000)

    def delete_selected(self) -> None:
        if not self._selected:
            return
        answer = QMessageBox.warning(
            self,
            "删除配置档案",
            f"确定删除 {self._selected} 吗？\n此操作不会删除已经下载的媒体文件。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_profile(self._selected)
        except ProfileError as exc:
            self._show_error(str(exc))
            return
        self._selected = None
        self.refresh_profiles()

    def start_or_stop(self) -> None:
        if not self._selected:
            return
        try:
            if self.jobs.is_active(self._selected):
                self.jobs.stop(self._selected)
            else:
                if self.editor.dirty and not self.save_selected():
                    return
                self.jobs.start(self._selected)
        except ProfileError as exc:
            self._show_error(str(exc))

    def _on_job_updated(self, filename: str, status: str) -> None:
        self.rail.update_status(filename, status)
        self.operations.refresh(self.jobs)
        if filename == self._selected:
            self.editor.set_enabled(status not in ACTIVE_STATES)
        self.statusBar().showMessage(f"{filename}: {STATUS_LABELS.get(status, status)}", 3000)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "操作失败", message)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.jobs.active_count():
            answer = QMessageBox.question(
                self,
                "退出控制台",
                "仍有下载任务正在运行。退出会停止这些任务，是否继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.jobs.shutdown()
        event.accept()


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 Twitter Download 原生桌面 GUI")
    parser.parse_args()
    application = QApplication(sys.argv[:1])
    application.setApplicationName("Archive Signal Desk")
    application.setOrganizationName("Twitter Download")
    application.setStyle("Fusion")
    application.setFont(QFont("Microsoft YaHei UI", 9))
    application.setStyleSheet(build_stylesheet())
    window = MainWindow()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
