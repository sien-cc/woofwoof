#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首次运行配置向导"""

import json
import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QMessageBox,
    QFileDialog,
    QCheckBox,
    QGroupBox,
)


class SetupWizard(QDialog):
    def __init__(self, app_dir, parent=None):
        super().__init__(parent)
        self.app_dir = Path(app_dir)
        self.config_path = self.app_dir / "config.json"
        self.example_config_path = self.app_dir / "config.example.json"

        self.setWindowTitle("小爪子 - 首次运行配置")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # 欢迎标题
        title = QLabel("🐙 欢迎使用小爪子桌面宠物！")
        title.setStyleSheet("font-size: 18pt; font-weight: bold; color: #de886d;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        intro = QLabel(
            "这是你第一次运行小爪子，让我们快速配置一下吧！\n"
            "只需要几个简单的步骤，小爪子就能陪伴你了。"
        )
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignCenter)
        intro.setStyleSheet("font-size: 11pt; color: #666;")
        layout.addWidget(intro)

        # API Key 配置
        api_group = QGroupBox("1. API Key 配置")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        api_layout = QVBoxLayout()

        api_hint = QLabel(
            "小爪子需要 Claude API Key 才能和你聊天。\n"
            "你可以在 https://console.anthropic.com/ 获取 API Key。"
        )
        api_hint.setWordWrap(True)
        api_hint.setStyleSheet("color: #666; font-size: 9pt;")
        api_layout.addWidget(api_hint)

        api_input_layout = QHBoxLayout()
        api_label = QLabel("API Key:")
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-ant-...")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_input_layout.addWidget(api_label)
        api_input_layout.addWidget(self.api_key_input, 1)
        api_layout.addLayout(api_input_layout)

        self.use_env_var = QCheckBox("使用环境变量 CLAUDE_API_KEY（推荐）")
        self.use_env_var.setChecked(True)
        self.use_env_var.toggled.connect(self.toggle_api_input)
        api_layout.addWidget(self.use_env_var)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 存储路径配置
        path_group = QGroupBox("2. 笔记存储路径")
        path_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        path_layout = QVBoxLayout()

        path_hint = QLabel(
            "选择一个文件夹来保存聊天记录、人设和日记。\n"
            "默认会在程序目录的上级创建 pet_notes 文件夹。"
        )
        path_hint.setWordWrap(True)
        path_hint.setStyleSheet("color: #666; font-size: 9pt;")
        path_layout.addWidget(path_hint)

        path_input_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        default_path = str((self.app_dir.parent / "pet_notes").resolve())
        self.path_input.setText(default_path)
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.browse_path)
        path_input_layout.addWidget(self.path_input, 1)
        path_input_layout.addWidget(browse_button)
        path_layout.addLayout(path_input_layout)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # 人设和日记
        memory_group = QGroupBox("3. 初始化人设和日记")
        memory_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        memory_layout = QVBoxLayout()

        memory_hint = QLabel(
            "我们会为你创建人设和日记的模板文件。\n"
            "你可以稍后编辑这些文件来让小爪子更了解你！"
        )
        memory_hint.setWordWrap(True)
        memory_hint.setStyleSheet("color: #666; font-size: 9pt;")
        memory_layout.addWidget(memory_hint)

        self.create_templates = QCheckBox("创建人设和日记模板（推荐）")
        self.create_templates.setChecked(True)
        memory_layout.addWidget(self.create_templates)

        memory_group.setLayout(memory_layout)
        layout.addWidget(memory_group)

        layout.addStretch()

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)

        finish_button = QPushButton("完成配置 ✨")
        finish_button.setStyleSheet(
            """
            QPushButton {
                background-color: #de886d;
                color: white;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c97258;
            }
            """
        )
        finish_button.clicked.connect(self.finish_setup)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(finish_button)
        layout.addLayout(button_layout)

        self.toggle_api_input(True)

    def toggle_api_input(self, checked):
        """切换 API Key 输入框的启用状态"""
        self.api_key_input.setEnabled(not checked)
        if checked:
            self.api_key_input.setPlaceholderText("将从环境变量 CLAUDE_API_KEY 读取")
        else:
            self.api_key_input.setPlaceholderText("sk-ant-...")

    def browse_path(self):
        """浏览文件夹"""
        path = QFileDialog.getExistingDirectory(
            self,
            "选择笔记存储路径",
            self.path_input.text()
        )
        if path:
            self.path_input.setText(path)

    def finish_setup(self):
        """完成配置"""
        # 验证输入
        if not self.use_env_var.isChecked():
            api_key = self.api_key_input.text().strip()
            if not api_key:
                QMessageBox.warning(self, "提示", "请输入 API Key 或选择使用环境变量！")
                return
            if not api_key.startswith("sk-ant-"):
                reply = QMessageBox.question(
                    self,
                    "确认",
                    "你输入的 API Key 格式看起来不太对（通常以 sk-ant- 开头）。\n确定要继续吗？",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
        else:
            # 检查环境变量是否存在
            if not os.environ.get("CLAUDE_API_KEY"):
                reply = QMessageBox.question(
                    self,
                    "提示",
                    "环境变量 CLAUDE_API_KEY 尚未设置。\n"
                    "你需要在系统环境变量中设置它，否则小爪子无法工作。\n\n"
                    "是否继续？（你可以稍后设置环境变量）",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return

        notes_path = Path(self.path_input.text().strip())
        if not notes_path:
            QMessageBox.warning(self, "提示", "请选择笔记存储路径！")
            return

        try:
            # 创建配置文件
            self.create_config(notes_path)

            # 创建笔记目录和模板
            if self.create_templates.isChecked():
                self.create_notes_structure(notes_path)

            QMessageBox.information(
                self,
                "配置完成",
                "配置已完成！小爪子即将启动。\n\n"
                f"配置文件：{self.config_path}\n"
                f"笔记路径：{notes_path}\n\n"
                "你可以随时编辑配置文件和笔记来调整小爪子的行为。"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "错误",
                f"配置过程中出现错误：\n{str(e)}\n\n请检查路径权限或联系开发者。"
            )

    def create_config(self, notes_path):
        """创建配置文件"""
        # 从示例配置读取
        if self.example_config_path.exists():
            with open(self.example_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # 如果没有示例配置，创建一个基础配置
            config = {
                "api_base_url": "https://api.anthropic.com",
                "model": "claude-opus-4-6",
                "api_key_env": "CLAUDE_API_KEY",
                "api_timeout": 180,
                "save_chat_logs": True,
                "load_today_chat_into_context": False,
                "chat_context_max_messages": 20,
                "screenshot_interval": 5,
                "screenshot_single_hotkey": "shift+mouse4",
                "screenshot_continuous_hotkey": "ctrl+mouse4",
                "screenshot_whitelist": {
                    "enabled": False,
                    "prefer": "foreground",
                    "titles": [],
                    "processes": []
                }
            }

        # 更新配置
        config["diary_path"] = str(notes_path)
        config["autobiography_file"] = "人设.md"
        config["diary_file"] = "日记.md"

        # 如果用户直接输入了 API Key，保存到配置
        if not self.use_env_var.isChecked():
            api_key = self.api_key_input.text().strip()
            config["api_key"] = api_key
            config.pop("api_key_env", None)

        # 保存配置
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def create_notes_structure(self, notes_path):
        """创建笔记目录结构和模板文件"""
        notes_path = Path(notes_path)
        notes_path.mkdir(parents=True, exist_ok=True)

        # 复制模板文件
        templates_dir = self.app_dir / "templates"

        person_template = templates_dir / "人设模板.md"
        diary_template = templates_dir / "日记模板.md"

        person_dest = notes_path / "人设.md"
        diary_dest = notes_path / "日记.md"

        # 只在文件不存在时复制
        if not person_dest.exists() and person_template.exists():
            shutil.copy2(person_template, person_dest)

        if not diary_dest.exists() and diary_template.exists():
            shutil.copy2(diary_template, diary_dest)


def should_show_wizard(app_dir):
    """检查是否需要显示配置向导"""
    config_path = Path(app_dir) / "config.json"
    return not config_path.exists()


def run_wizard(app_dir):
    """运行配置向导"""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    wizard = SetupWizard(app_dir)
    result = wizard.exec()

    return result == QDialog.Accepted


if __name__ == "__main__":
    # 测试
    app_dir = Path(__file__).resolve().parent
    if should_show_wizard(app_dir):
        success = run_wizard(app_dir)
        if success:
            print("配置完成！")
        else:
            print("用户取消了配置。")
    else:
        print("配置文件已存在。")
