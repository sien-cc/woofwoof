#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首次运行配置向导 - 简化版"""

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
    QRadioButton,
    QButtonGroup,
)


class SetupWizard(QDialog):
    def __init__(self, app_dir, parent=None):
        super().__init__(parent)
        self.app_dir = Path(app_dir)
        self.config_path = self.app_dir / "config.json"
        self.example_config_path = self.app_dir / "config.example.json"

        self.setWindowTitle("小爪子 - 首次运行配置")
        self.setMinimumSize(600, 700)
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
            "只需要填写 API 信息，小爪子就能陪伴你了。"
        )
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignCenter)
        intro.setStyleSheet("font-size: 11pt; color: #666;")
        layout.addWidget(intro)

        # 预设选择
        preset_group = QGroupBox("1. 选择预设（可选）")
        preset_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        preset_layout = QVBoxLayout()

        self.preset_buttons = QButtonGroup(self)

        presets = [
            ("none", "不使用预设（手动填写）", "", ""),
            ("claude", "Claude 官方", "https://api.anthropic.com", "claude-opus-4-6"),
            ("openai", "OpenAI 官方", "https://api.openai.com", "gpt-4"),
            ("gemini", "Gemini 官方", "https://generativelanguage.googleapis.com/v1beta", "gemini-3.5-flash"),
            ("deepseek", "DeepSeek 官方", "https://api.deepseek.com", "deepseek-chat"),
        ]

        for i, (preset_id, display_name, url, model) in enumerate(presets):
            radio = QRadioButton(display_name)
            radio.setProperty("preset_id", preset_id)
            radio.setProperty("preset_url", url)
            radio.setProperty("preset_model", model)
            self.preset_buttons.addButton(radio, i)
            preset_layout.addWidget(radio)
            if preset_id == "none":
                radio.setChecked(True)

        self.preset_buttons.buttonClicked.connect(self.on_preset_changed)
        preset_group.setLayout(preset_layout)
        layout.addWidget(preset_group)

        # API 配置
        api_group = QGroupBox("2. API 配置")
        api_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        api_layout = QVBoxLayout()

        # API 地址
        api_url_layout = QHBoxLayout()
        api_url_label = QLabel("API 地址:")
        api_url_label.setMinimumWidth(80)
        self.api_url_input = QLineEdit()
        self.api_url_input.setPlaceholderText("https://api.anthropic.com 或中转地址")
        api_url_layout.addWidget(api_url_label)
        api_url_layout.addWidget(self.api_url_input)
        api_layout.addLayout(api_url_layout)

        # 模型名称
        model_layout = QHBoxLayout()
        model_label = QLabel("模型名称:")
        model_label.setMinimumWidth(80)
        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("claude-opus-4-6 或 gpt-4 等")
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        api_layout.addLayout(model_layout)

        # API Key
        api_key_layout = QHBoxLayout()
        api_key_label = QLabel("API Key:")
        api_key_label.setMinimumWidth(80)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("sk-ant-... 或环境变量名")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        api_key_layout.addWidget(api_key_label)
        api_key_layout.addWidget(self.api_key_input)
        api_layout.addLayout(api_key_layout)

        self.use_env_var = QCheckBox("使用环境变量存储 API Key（推荐）")
        self.use_env_var.setChecked(True)
        self.use_env_var.toggled.connect(self.toggle_api_input)
        api_layout.addWidget(self.use_env_var)

        api_hint = QLabel(
            "提示：\n"
            "• 使用环境变量时，填写变量名（如 CLAUDE_API_KEY）\n"
            "• 不使用环境变量时，直接填写完整 API Key\n"
            "• 中转 API 通常兼容 OpenAI 格式，直接填中转地址即可"
        )
        api_hint.setWordWrap(True)
        api_hint.setStyleSheet("color: #888; font-size: 9pt; margin-top: 5px;")
        api_layout.addWidget(api_hint)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 高级选项
        advanced_group = QGroupBox("3. 高级选项（可选）")
        advanced_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        advanced_layout = QVBoxLayout()

        # API 格式
        format_layout = QHBoxLayout()
        format_label = QLabel("API 格式:")
        format_label.setMinimumWidth(80)
        self.format_buttons = QButtonGroup(self)

        openai_radio = QRadioButton("OpenAI 兼容（默认）")
        openai_radio.setProperty("format", "openai")
        openai_radio.setChecked(True)
        self.format_buttons.addButton(openai_radio)

        claude_radio = QRadioButton("Claude 官方")
        claude_radio.setProperty("format", "claude")
        self.format_buttons.addButton(claude_radio)

        gemini_radio = QRadioButton("Gemini 官方")
        gemini_radio.setProperty("format", "gemini")
        self.format_buttons.addButton(gemini_radio)

        format_layout.addWidget(format_label)
        format_layout.addWidget(openai_radio)
        format_layout.addWidget(claude_radio)
        format_layout.addWidget(gemini_radio)
        advanced_layout.addLayout(format_layout)

        # Claude 思维链
        self.enable_thinking = QCheckBox("启用 Claude 思维链（仅 Claude 官方格式）")
        self.enable_thinking.setChecked(True)
        advanced_layout.addWidget(self.enable_thinking)

        advanced_hint = QLabel(
            "• 大部分中转 API 使用 OpenAI 兼容格式\n"
            "• 只有直连 Claude 官方或支持 Claude 格式的中转才选 Claude 官方"
        )
        advanced_hint.setWordWrap(True)
        advanced_hint.setStyleSheet("color: #888; font-size: 9pt; margin-top: 5px;")
        advanced_layout.addWidget(advanced_hint)

        advanced_group.setLayout(advanced_layout)
        layout.addWidget(advanced_group)

        # 存储路径
        path_group = QGroupBox("4. 数据存储路径")
        path_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        path_layout = QVBoxLayout()

        diary_layout = QHBoxLayout()
        diary_label = QLabel("笔记路径:")
        diary_label.setMinimumWidth(80)
        self.diary_path_input = QLineEdit()
        default_notes_path = str((self.app_dir.parent / "pet_notes").resolve())
        self.diary_path_input.setText(default_notes_path)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.browse_diary_path)
        diary_layout.addWidget(diary_label)
        diary_layout.addWidget(self.diary_path_input)
        diary_layout.addWidget(browse_btn)
        path_layout.addLayout(diary_layout)

        path_hint = QLabel("小爪子会在这里保存聊天记录、日记和自传")
        path_hint.setStyleSheet("color: #888; font-size: 9pt;")
        path_layout.addWidget(path_hint)

        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # 按钮
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("保存配置")
        save_btn.setStyleSheet("QPushButton { background: #de886d; color: white; font-weight: bold; padding: 8px 20px; }")
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # 初始化输入框状态
        self.toggle_api_input(True)

    def on_preset_changed(self):
        """预设改变时自动填充"""
        button = self.preset_buttons.checkedButton()
        if not button:
            return

        url = button.property("preset_url")
        model = button.property("preset_model")
        preset_id = button.property("preset_id")

        if url:
            self.api_url_input.setText(url)
        if model:
            self.model_input.setText(model)

        # 根据预设设置格式
        if preset_id == "claude":
            for btn in self.format_buttons.buttons():
                if btn.property("format") == "claude":
                    btn.setChecked(True)
                    break
        elif preset_id == "gemini":
            for btn in self.format_buttons.buttons():
                if btn.property("format") == "gemini":
                    btn.setChecked(True)
                    break
        else:
            for btn in self.format_buttons.buttons():
                if btn.property("format") == "openai":
                    btn.setChecked(True)
                    break

    def toggle_api_input(self, use_env):
        """切换 API Key 输入模式"""
        if use_env:
            self.api_key_input.setPlaceholderText("环境变量名（如 CLAUDE_API_KEY）")
            self.api_key_input.setEchoMode(QLineEdit.Normal)
            self.api_key_input.setText("CLAUDE_API_KEY")
        else:
            self.api_key_input.setPlaceholderText("完整 API Key（如 sk-ant-...）")
            self.api_key_input.setEchoMode(QLineEdit.Password)
            self.api_key_input.clear()

    def browse_diary_path(self):
        """浏览笔记路径"""
        path = QFileDialog.getExistingDirectory(
            self, "选择笔记存储路径", self.diary_path_input.text()
        )
        if path:
            self.diary_path_input.setText(path)

    def save_config(self):
        """保存配置"""
        api_url = self.api_url_input.text().strip()
        model = self.model_input.text().strip()
        api_key_input = self.api_key_input.text().strip()
        diary_path = self.diary_path_input.text().strip()
        use_env = self.use_env_var.isChecked()

        # 验证必填项
        if not api_url:
            QMessageBox.warning(self, "配置错误", "请填写 API 地址")
            return
        if not model:
            QMessageBox.warning(self, "配置错误", "请填写模型名称")
            return
        if not api_key_input:
            QMessageBox.warning(self, "配置错误", "请填写 API Key 或环境变量名")
            return
        if not diary_path:
            QMessageBox.warning(self, "配置错误", "请选择笔记存储路径")
            return

        # 获取 API 格式
        api_format = "openai"
        for btn in self.format_buttons.buttons():
            if btn.isChecked():
                api_format = btn.property("format")
                break

        # 构建配置
        try:
            # 加载示例配置作为模板
            with open(self.example_config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 创建主配置
            main_config = {
                "name": "1. 主配置",
                "api_base_url": api_url,
                "model": model,
                "format": api_format
            }

            if use_env:
                main_config["api_key"] = ""
                main_config["api_key_env"] = api_key_input
            else:
                main_config["api_key"] = api_key_input
                main_config["api_key_env"] = ""

            # Claude 官方格式的思维链配置
            if api_format == "claude" and self.enable_thinking.isChecked():
                main_config["enable_thinking"] = True
                main_config["thinking_budget_tokens"] = 10000

            config["current_config"] = "main"
            config["api_configs"] = {
                "main": main_config
            }

            # 更新笔记路径
            config["diary_path"] = diary_path

            # 确保笔记目录存在
            diary_path_obj = Path(diary_path)
            diary_path_obj.mkdir(parents=True, exist_ok=True)

            # 保存配置
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            QMessageBox.information(
                self,
                "配置成功",
                "配置已保存！小爪子即将启动。\n\n"
                "提示：可以在配置文件中添加更多 API 配置，右键小爪子即可切换。"
            )
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self, "保存失败", f"保存配置时出错：\n{str(e)}"
            )


def main():
    app = QApplication(sys.argv)

    # 获取应用目录
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).parent

    wizard = SetupWizard(app_dir)
    if wizard.exec() == QDialog.Accepted:
        print("配置完成")
    else:
        print("取消配置")

    sys.exit(0)


if __name__ == "__main__":
    main()
