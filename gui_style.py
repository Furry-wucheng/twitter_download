"""Visual system for the PySide6 control desk."""

from __future__ import annotations


def build_stylesheet() -> str:
    return """
    * {
        font-family: "Microsoft YaHei UI", "Segoe UI";
        font-size: 13px;
        color: #d9dedb;
    }

    QMainWindow, QWidget#appRoot {
        background: #091011;
    }

    QFrame#masthead {
        background: #0d1517;
        border: 1px solid #243033;
        border-radius: 12px;
    }

    QLabel#brandMark {
        background: #e9a23b;
        color: #101617;
        border-radius: 8px;
        font-family: "Bahnschrift SemiBold";
        font-size: 20px;
        font-weight: 700;
        qproperty-alignment: AlignCenter;
    }

    QLabel#brandTitle {
        color: #f2eee3;
        font-family: "Bahnschrift SemiCondensed";
        font-size: 19px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    QLabel#brandSubtitle, QLabel#headerMeta, QLabel#muted,
    QLabel#sectionCode, QLabel#fieldHint {
        color: #829094;
    }

    QLabel#headerMeta {
        font-family: "Cascadia Mono", "Consolas";
        font-size: 11px;
    }

    QLabel#clock {
        color: #65d7c7;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 13px;
        font-weight: 600;
    }

    QFrame#darkPanel {
        background: #10191b;
        border: 1px solid #293638;
        border-radius: 14px;
    }

    QFrame#paperPanel {
        background: #e8e3d6;
        border: 1px solid #5e625c;
        border-radius: 14px;
    }

    QFrame#paperPanel QLabel,
    QFrame#paperPanel QCheckBox,
    QFrame#paperPanel QRadioButton {
        color: #1a2425;
    }

    QLabel#panelTitle {
        color: #f2eee3;
        font-family: "Bahnschrift SemiCondensed";
        font-size: 22px;
        font-weight: 700;
    }

    QFrame#paperPanel QLabel#panelTitle {
        color: #172021;
    }

    QLabel#panelKicker {
        color: #e9a23b;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1px;
    }

    QFrame#paperPanel QLabel#panelKicker {
        color: #8b5a12;
    }

    QPushButton {
        min-height: 34px;
        padding: 0 15px;
        background: #182426;
        color: #e9ece8;
        border: 1px solid #344244;
        border-radius: 8px;
        font-weight: 600;
    }

    QPushButton:hover {
        background: #213033;
        border-color: #59696b;
    }

    QPushButton:pressed {
        background: #101819;
    }

    QPushButton:disabled {
        color: #687274;
        background: #151d1f;
        border-color: #293234;
    }

    QPushButton#primaryButton {
        background: #e9a23b;
        color: #101617;
        border-color: #f0b45f;
    }

    QPushButton#primaryButton:hover {
        background: #f0b45f;
    }

    QPushButton#runButton {
        min-height: 48px;
        background: #65d7c7;
        color: #0d1819;
        border: 0;
        border-radius: 9px;
        font-family: "Bahnschrift SemiCondensed";
        font-size: 15px;
        font-weight: 700;
    }

    QPushButton#runButton:hover {
        background: #83e3d6;
    }

    QPushButton#runButton[running="true"] {
        background: #e45d4f;
        color: #fff2ec;
    }

    QPushButton#dangerButton {
        color: #ad4239;
        background: transparent;
        border-color: #b88d84;
    }

    QToolButton {
        min-width: 34px;
        min-height: 34px;
        background: #172225;
        color: #e9a23b;
        border: 1px solid #374649;
        border-radius: 8px;
        font-size: 17px;
        font-weight: 700;
    }

    QToolButton:hover {
        background: #223034;
        border-color: #e9a23b;
    }

    QListWidget#profileList, QListWidget#jobList {
        background: transparent;
        border: 0;
        outline: 0;
    }

    QListWidget#profileList::item, QListWidget#jobList::item {
        background: transparent;
        border: 0;
        margin: 3px 0;
    }

    QFrame#profileItem {
        background: #131f21;
        border: 1px solid #29383a;
        border-radius: 10px;
    }

    QFrame#profileItem:hover {
        border-color: #506163;
        background: #172426;
    }

    QFrame#profileItem[selected="true"] {
        background: #1d2a2b;
        border: 2px solid #e9a23b;
    }

    QFrame#profileItem QLabel#profileName {
        color: #f0ede3;
        font-size: 14px;
        font-weight: 700;
    }

    QFrame#profileItem QLabel#profileMeta {
        color: #7f8d90;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 10px;
    }

    QLabel#statusPill {
        background: #263235;
        color: #9aa5a7;
        border-radius: 7px;
        padding: 2px 7px;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 9px;
        font-weight: 700;
    }

    QLabel#statusPill[status="running"], QLabel#statusPill[status="starting"] {
        background: #17463f;
        color: #7be0d1;
    }

    QLabel#statusPill[status="completed"] {
        background: #354422;
        color: #c8df80;
    }

    QLabel#statusPill[status="failed"] {
        background: #512722;
        color: #f29a8d;
    }

    QLabel#statusPill[status="stopping"], QLabel#statusPill[status="stopped"] {
        background: #4b3b22;
        color: #e8bd70;
    }

    QScrollArea#editorScroll {
        background: transparent;
        border: 0;
    }

    QScrollArea#editorScroll > QWidget > QWidget {
        background: transparent;
    }

    QFrame#sectionCard {
        background: #f2eee3;
        border: 1px solid #cbc4b2;
        border-radius: 10px;
    }

    QFrame#sectionCard QLabel#sectionTitle {
        color: #182223;
        font-family: "Bahnschrift SemiCondensed";
        font-size: 16px;
        font-weight: 700;
    }

    QFrame#sectionCard QLabel#sectionCode {
        color: #9b6a21;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 9px;
        font-weight: 700;
    }

    QFrame#sectionCard QLabel#fieldLabel {
        color: #3f4a4a;
        font-size: 11px;
        font-weight: 600;
    }

    QLineEdit, QDateEdit, QSpinBox, QComboBox, QPlainTextEdit {
        min-height: 35px;
        padding: 0 10px;
        background: #fffdf6;
        color: #172021;
        border: 1px solid #b9b4a7;
        border-radius: 7px;
        selection-background-color: #65d7c7;
        selection-color: #102021;
    }

    QLineEdit:hover, QDateEdit:hover, QSpinBox:hover, QComboBox:hover {
        border-color: #82877f;
    }

    QLineEdit:focus, QDateEdit:focus, QSpinBox:focus, QComboBox:focus {
        border: 2px solid #318f84;
        padding: 0 9px;
    }

    QLineEdit:disabled, QDateEdit:disabled, QSpinBox:disabled, QComboBox:disabled {
        color: #8c8f88;
        background: #dedbd1;
    }

    QComboBox::drop-down, QDateEdit::drop-down {
        border: 0;
        width: 26px;
    }

    QComboBox QAbstractItemView {
        background: #fffdf6;
        color: #172021;
        border: 1px solid #8e938b;
        selection-background-color: #d6eee9;
    }

    QCheckBox, QRadioButton {
        spacing: 8px;
        min-height: 26px;
    }

    QCheckBox::indicator, QRadioButton::indicator {
        width: 17px;
        height: 17px;
        background: #fffdf6;
        border: 1px solid #8e938b;
    }

    QCheckBox::indicator {
        border-radius: 4px;
    }

    QRadioButton::indicator {
        border-radius: 9px;
    }

    QCheckBox::indicator:checked {
        background: #258b80;
        border: 4px solid #d7f0eb;
    }

    QRadioButton::indicator:checked {
        background: #e9a23b;
        border: 4px solid #fff4df;
    }

    QSlider::groove:horizontal {
        height: 5px;
        background: #c6c1b4;
        border-radius: 2px;
    }

    QSlider::sub-page:horizontal {
        background: #258b80;
        border-radius: 2px;
    }

    QSlider::handle:horizontal {
        width: 17px;
        margin: -6px 0;
        background: #172021;
        border: 2px solid #65d7c7;
        border-radius: 8px;
    }

    QFrame#launchCard {
        background: #e9a23b;
        border-radius: 10px;
    }

    QFrame#launchCard QLabel {
        color: #111819;
    }

    QFrame#launchCard QLabel#launchName {
        font-family: "Bahnschrift SemiCondensed";
        font-size: 17px;
        font-weight: 700;
    }

    QListWidget#jobList {
        background: #0c1416;
        border: 1px solid #253234;
        border-radius: 9px;
        padding: 5px;
    }

    QListWidget#jobList::item {
        color: #bcc5c4;
        padding: 8px;
        border-radius: 6px;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 11px;
    }

    QListWidget#jobList::item:selected {
        background: #203034;
        color: #65d7c7;
    }

    QPlainTextEdit#console {
        min-height: 260px;
        background: #070d0e;
        color: #b8c6c3;
        border: 1px solid #293638;
        border-radius: 9px;
        padding: 10px;
        font-family: "Cascadia Mono", "Consolas";
        font-size: 11px;
        selection-background-color: #355f5b;
        selection-color: #ffffff;
    }

    QDialog {
        background: #111a1c;
    }

    QDialog QLabel#dialogTitle {
        color: #f2eee3;
        font-family: "Bahnschrift SemiCondensed";
        font-size: 23px;
        font-weight: 700;
    }

    QDialog QLabel#fieldLabel {
        color: #aeb8b7;
    }

    QMessageBox {
        background: #111a1c;
    }

    QStatusBar {
        background: #0b1214;
        color: #93a09f;
        border-top: 1px solid #243033;
    }

    QScrollBar:vertical {
        width: 10px;
        background: transparent;
        margin: 3px;
    }

    QScrollBar::handle:vertical {
        min-height: 32px;
        background: #65706d;
        border-radius: 4px;
    }

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
        height: 0;
        background: transparent;
    }
    """
