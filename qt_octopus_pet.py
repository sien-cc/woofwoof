#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PySide6 desktop pet main program."""

import ctypes
import os
import re
import sys
import threading
import time
from pathlib import Path

import requests
from PySide6.QtCore import QObject, QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QMovie, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication, QFrame, QVBoxLayout, QLabel, QWidget

from pet_core import (
    ChatLogStore,
    ClaudeClient,
    ConversationService,
    MarkdownNoteStore,
    MissingApiKeyError,
    PetNoteActionHandler,
    ScreenshotService,
    get_notes_root,
    get_ui_config,
    load_config_file,
    load_diary_files,
    validate_config,
    setup_logging,
)
from pet_emotions import GIF_EMOTIONS, IDLE_ACTIONS, SVG_EMOTIONS, SVG_SCALE
from pet_ui import (
    ASSISTANT_BUBBLE_MIN_HEIGHT,
    ASSISTANT_BUBBLE_MIN_WIDTH,
    BUBBLE_GAP,
    HISTORY_WINDOW_PET_GAP,
    PET_SIZE,
    PET_WINDOW_GAP,
    USER_BUBBLE_MIN_HEIGHT,
    USER_BUBBLE_MIN_WIDTH,
    WINDOW_MARGIN,
)
from qt_pet_ui import ChatBubble, ChatWindow, HistoryDrawer, InputBar


class ConversationSignals(QObject):
    reply_ready = Signal(str, str, str, str)  # message, emotion, source, thinking
    error_ready = Signal(str, str, str)
    status_ready = Signal(str, str)
    toggle_continuous_screenshot_requested = Signal()
    single_screenshot_requested = Signal()


class FloatingBubble(QFrame):
    def __init__(self, role, message):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        bubble = ChatBubble(message, role=role)
        layout.addWidget(bubble)
        self.adjustSize()


class ErrorBubbleWithRetry(QFrame):
    """带重试/取消按钮的错误气泡"""
    retry_clicked = Signal()
    cancel_clicked = Signal()

    def __init__(self, message):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 错误消息气泡
        bubble = ChatBubble(message, role="assistant")
        layout.addWidget(bubble)

        # 按钮容器
        from PySide6.QtWidgets import QPushButton, QHBoxLayout
        button_container = QFrame()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(10, 5, 10, 10)
        button_layout.setSpacing(10)

        # 重试按钮
        retry_button = QPushButton("🔄 重试")
        retry_button.setStyleSheet("""
            QPushButton {
                background-color: #4A9EFF;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #3A8EEF;
            }
            QPushButton:pressed {
                background-color: #2A7EDF;
            }
        """)
        retry_button.clicked.connect(self.retry_clicked.emit)

        # 取消按钮
        cancel_button = QPushButton("❌ 取消")
        cancel_button.setStyleSheet("""
            QPushButton {
                background-color: #E0E0E0;
                color: #333;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
        """)
        cancel_button.clicked.connect(self.cancel_clicked.emit)

        button_layout.addWidget(retry_button)
        button_layout.addWidget(cancel_button)
        layout.addWidget(button_container)

        self.adjustSize()


class PetAnimator(QObject):
    IDLE_ACTIONS = IDLE_ACTIONS
    EMOTIONS = GIF_EMOTIONS
    SVG_EMOTIONS = SVG_EMOTIONS
    SVG_SCALE = SVG_SCALE
    svg_frames_ready = Signal(str, object, int)

    def __init__(self, label, app_dir, config):
        super().__init__(label)
        self.label = label
        self.config = config
        self.render_size = max(1, label.width())

        # 从配置读取资源路径
        gif_path = config.get('assets_path', 'gif')
        svg_path = config.get('svg_assets_path', 'svg')
        self.gif_dir = Path(app_dir) / gif_path
        self.svg_dir = Path(app_dir) / svg_path
        self.frame_animations = {}
        self.pixmaps = {}
        self.svg_rendering = set()
        self.current_name = None
        self.steady_emotion = "idle"
        self.frame_index = 0
        self.frame_timer = QTimer(self)
        self.frame_timer.timeout.connect(self.advance_frame)
        self.svg_frames_ready.connect(self.on_svg_frames_ready)
        self.idle_index = 0
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.timeout.connect(self.play_idle_action)
        self.return_timer = QTimer(self)
        self.return_timer.setSingleShot(True)
        self.return_timer.timeout.connect(self.return_to_steady)
        self.active_reaction_name = None
        self.active_reaction_duration = 0

        # 从配置读取 SVG 渲染参数
        self.SVG_FRAME_RATE = get_ui_config(config, 'svg_rendering', 'frame_rate', default=12)
        self.SVG_MAX_FRAMES = get_ui_config(config, 'svg_rendering', 'max_frames', default=120)
        self.SVG_DEFAULT_SCALE = get_ui_config(config, 'svg_rendering', 'default_scale', default=1.0)
        self.pixmap_cache_limit = get_ui_config(config, 'svg_rendering', 'pixmap_cache_limit', default=20)

    def set_steady(self, name):
        self.steady_emotion = name if self.has_emotion(name) else "idle"
        self.idle_timer.stop()
        self.return_timer.stop()
        self.clear_reaction()
        self.set_emotion(self.steady_emotion)
        if self.steady_emotion == "idle":
            self.schedule_idle_action()

    def play_reaction(self, name=None, duration=None, fallback=None):
        self.idle_timer.stop()
        if not name:
            name = fallback or self.steady_emotion
        if not self.has_emotion(name):
            name = fallback or self.steady_emotion
        # 使用配置的默认时长
        if duration is None:
            duration = get_ui_config(self.config, 'animations', 'reaction_default_ms', default=2600)
        self.active_reaction_name = name
        self.active_reaction_duration = duration
        self.set_emotion(name)
        self.start_reaction_return_timer(name, duration)

    def play_error(self):
        duration = get_ui_config(self.config, 'animations', 'reaction_error_ms', default=3200)
        self.play_reaction("error", duration=duration, fallback="idle")

    def mark_activity(self):
        self.idle_timer.stop()
        self.return_timer.stop()
        self.clear_reaction()
        if self.steady_emotion == "idle":
            self.set_emotion("idle")
            self.schedule_idle_action()

    def schedule_idle_action(self, delay_ms=None):
        if self.steady_emotion == "idle" and self.available_idle_actions():
            if delay_ms is None:
                delay_ms = get_ui_config(self.config, 'animations', 'idle_action_delay_ms', default=9000)
            self.idle_timer.start(delay_ms)

    def play_idle_action(self):
        actions = self.available_idle_actions()
        if self.steady_emotion != "idle" or not actions:
            return
        action = actions[self.idle_index % len(actions)]
        self.idle_index += 1
        duration = get_ui_config(self.config, 'animations', 'idle_action_duration_ms', default=5200)
        self.play_reaction(action, duration=duration, fallback="idle")

    def available_idle_actions(self):
        return [name for name in self.IDLE_ACTIONS if self.has_emotion(name)]

    def return_to_steady(self):
        self.clear_reaction()
        self.set_emotion(self.steady_emotion)

    def clear_reaction(self):
        self.active_reaction_name = None
        self.active_reaction_duration = 0

    def start_reaction_return_timer(self, name, duration):
        if self.is_waiting_for_svg_frames(name):
            self.return_timer.start(max(duration + 6000, 8000))
            return
        self.return_timer.start(self.reaction_return_duration(name, duration))

    def is_waiting_for_svg_frames(self, name):
        return (
            name in self.SVG_EMOTIONS
            and name in self.svg_rendering
            and name not in self.frame_animations
        )

    def reaction_return_duration(self, name, fallback_duration):
        frames_data = self.frame_animations.get(name)
        if not frames_data:
            return fallback_duration
        frames, frame_delay = frames_data
        return max(fallback_duration, len(frames) * frame_delay + frame_delay)

    def has_emotion(self, name):
        gif_filename = self.EMOTIONS.get(name)
        svg_filename = self.SVG_EMOTIONS.get(name)
        return bool(
            (gif_filename and (self.gif_dir / gif_filename).exists())
            or (svg_filename and (self.svg_dir / svg_filename).exists())
        )

    def set_emotion(self, name):
        if name == self.current_name:
            if name in self.frame_animations and not self.frame_timer.isActive():
                self.frame_timer.start(self.frame_animations[name][1])
            return

        if name in self.SVG_EMOTIONS:
            self.request_svg_frames(name)
            if self.start_frame_animation(name) or self.show_static_svg(name):
                return

        if self.load_gif_animation(name) and self.start_frame_animation(name):
            return

        if name != "idle" and self.load_gif_animation("idle"):
            name = "idle"
            if self.start_frame_animation(name):
                return

        self.frame_timer.stop()
        self.current_name = None
        self.label.setMovie(None)
        self.label.setText(get_ui_config(self.config, 'text', 'window_title', default="Clawd"))
        self.label.setAlignment(Qt.AlignCenter)

    def load_gif_animation(self, name):
        if name in self.frame_animations:
            return True

        filename = self.EMOTIONS.get(name)
        if not filename:
            return False
        path = self.gif_dir / filename
        if not path.exists():
            return False

        movie = QMovie(str(path))
        frame_count = movie.frameCount()
        if frame_count <= 0:
            return False

        frames = []
        delays = []
        for frame_index in range(frame_count):
            if not movie.jumpToFrame(frame_index):
                continue
            frame = self.normalize_gif_frame(movie.currentPixmap())
            if frame.isNull():
                continue
            frames.append(frame)
            delays.append(max(20, movie.nextFrameDelay() or 70))

        if not frames:
            return False

        frame_delay = int(sum(delays) / len(delays)) if delays else 70
        self.frame_animations[name] = (frames, frame_delay)
        return True

    def normalize_gif_frame(self, pixmap):
        if pixmap.isNull():
            return QPixmap()
        scaled = pixmap.scaled(
            self.label.size(),
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        canvas = QPixmap(self.label.size())
        canvas.fill(QColor(0, 0, 0, 0))
        painter = QPainter(canvas)
        x = (canvas.width() - scaled.width()) // 2
        y = (canvas.height() - scaled.height()) // 2
        painter.drawPixmap(x, y, scaled)
        painter.end()
        return canvas

    def show_static_svg(self, name):
        pixmap = self.get_svg_pixmap(name)
        if pixmap is None:
            return False
        self.frame_timer.stop()
        self.current_name = name
        self.label.setMovie(None)
        self.label.setPixmap(pixmap)
        return True

    def start_frame_animation(self, name):
        frames_data = self.frame_animations.get(name)
        if not frames_data:
            return False
        frames, frame_delay = frames_data
        self.current_name = name
        self.frame_index = 0
        self.label.setMovie(None)
        self.label.setPixmap(frames[0])
        self.frame_timer.start(frame_delay)
        return True

    def request_svg_frames(self, name):
        if name in self.frame_animations or name in self.svg_rendering:
            return
        filename = self.SVG_EMOTIONS.get(name)
        if not filename or not (self.svg_dir / filename).exists():
            return

        self.svg_rendering.add(name)
        threading.Thread(target=self.render_svg_worker, args=(name,), daemon=True).start()

    def render_svg_worker(self, name):
        frames = []
        frame_delay = 100
        try:
            frames, frame_delay = self.render_svg_frame_bytes(name)
        except Exception:
            frames = []
        self.svg_frames_ready.emit(name, frames, frame_delay)

    def on_svg_frames_ready(self, name, frame_bytes, frame_delay):
        self.svg_rendering.discard(name)
        frames = []
        for png_bytes in frame_bytes or []:
            pixmap = QPixmap()
            if pixmap.loadFromData(png_bytes, "PNG"):
                frames.append(pixmap)
        if not frames:
            self.restart_reaction_timer_if_current(name)
            return
        self.frame_animations[name] = (frames, frame_delay)
        if self.current_name == name:
            self.start_frame_animation(name)
            self.restart_reaction_timer_if_current(name)

    def restart_reaction_timer_if_current(self, name):
        if self.current_name != name or self.active_reaction_name != name:
            return
        duration = self.reaction_return_duration(name, self.active_reaction_duration or 2600)
        self.return_timer.start(duration)

    def advance_frame(self):
        frames_data = self.frame_animations.get(self.current_name)
        if not frames_data:
            self.frame_timer.stop()
            return
        frames, _frame_delay = frames_data
        if not frames:
            self.frame_timer.stop()
            return
        self.frame_index = (self.frame_index + 1) % len(frames)
        self.label.setPixmap(frames[self.frame_index])

    def render_svg_frame_bytes(self, name):
        filename = self.SVG_EMOTIONS.get(name)
        if not filename:
            return [], 100
        path = self.svg_dir / filename
        if not path.exists():
            return [], 100

        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return [], 100

        svg_text = self.sanitize_svg(path.read_text(encoding="utf-8"))
        duration_ms = self.get_svg_duration_ms(svg_text)
        frame_count = min(
            self.SVG_MAX_FRAMES,
            max(1, int(duration_ms / 1000 * self.SVG_FRAME_RATE)),
        )
        frame_delay = max(20, int(duration_ms / frame_count))
        frames = []

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                java_script_enabled=False,
                offline=True,
                viewport={"width": self.render_size, "height": self.render_size},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.route("**/*", lambda route: route.abort())

            for frame_index in range(frame_count):
                time_ms = frame_index * frame_delay
                page.set_content(
                    self.build_svg_capture_html(svg_text, time_ms, self.svg_scale(name)),
                    wait_until="domcontentloaded",
                )
                frames.append(page.screenshot(omit_background=True))

            context.close()
            browser.close()

        return frames, frame_delay

    def get_svg_pixmap(self, name):
        if name in self.pixmaps:
            return self.pixmaps[name]

        # 如果缓存太多了，清空一半
        if len(self.pixmaps) > self.pixmap_cache_limit:
            recent_keys = list(self.pixmaps.keys())[-(self.pixmap_cache_limit // 2):]
            self.pixmaps = {k: self.pixmaps[k] for k in recent_keys}

        filename = self.SVG_EMOTIONS.get(name)
        if not filename:
            return None
        path = self.svg_dir / filename
        if not path.exists():
            return None

        renderer = QSvgRenderer(str(path))
        if not renderer.isValid():
            return None

        pixmap = QPixmap(self.label.size())
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        target = self.scaled_render_rect(name)
        renderer.render(painter, target)
        painter.end()
        self.pixmaps[name] = pixmap
        return pixmap

    def svg_scale(self, name):
        return self.SVG_SCALE.get(name, self.SVG_DEFAULT_SCALE)

    def scaled_render_rect(self, name):
        scale = self.svg_scale(name)
        size = self.label.width()
        render_size = size * scale
        offset = (size - render_size) / 2
        return QRectF(offset, offset, render_size, render_size)

    def sanitize_svg(self, svg_text):
        """清理SVG中的潜在危险内容"""
        # 移除 script 标签
        svg_text = re.sub(r"<script\b[^>]*>.*?</script>", "", svg_text, flags=re.DOTALL | re.IGNORECASE)
        # 移除 foreignObject (可以嵌入HTML)
        svg_text = re.sub(r"<foreignObject\b[^>]*>.*?</foreignObject>", "", svg_text, flags=re.DOTALL | re.IGNORECASE)
        # 移除事件处理器 (onclick, onload, etc.)
        svg_text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(\".*?\"|'.*?'|[^\s>]+)", "", svg_text, flags=re.DOTALL)
        # 移除 xml-stylesheet
        svg_text = re.sub(r"<\?xml-stylesheet\b[^>]*>", "", svg_text, flags=re.IGNORECASE)
        # 移除 CSS @import
        svg_text = re.sub(r"@import\s+[^;]+;", "", svg_text, flags=re.IGNORECASE)
        # 移除外部资源链接 (href, xlink:href, src)
        svg_text = re.sub(r"\s(?:href|xlink:href|src)\s*=\s*[\"'](?:https?:|file:|javascript:|data:)[^\"']*[\"']", "", svg_text, flags=re.IGNORECASE)
        # 移除 CSS url() 外部资源
        svg_text = re.sub(r"url\(\s*[\"']?(?:https?:|file:|javascript:|data:)[^)]+?\)", "none", svg_text, flags=re.IGNORECASE)
        # 移除 use 标签的外部引用 (可能指向恶意文件)
        svg_text = re.sub(r"<use\b[^>]*\shref\s*=\s*[\"']https?:[^\"']*[\"'][^>]*>", "", svg_text, flags=re.IGNORECASE)
        # 移除 iframe 标签 (如果有)
        svg_text = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", svg_text, flags=re.DOTALL | re.IGNORECASE)
        # 移除 embed 和 object 标签
        svg_text = re.sub(r"<(?:embed|object)\b[^>]*>.*?</(?:embed|object)>", "", svg_text, flags=re.DOTALL | re.IGNORECASE)

        return svg_text

    def get_svg_duration_ms(self, svg_text):
        durations = []
        for value, unit in re.findall(r"animation(?:-duration)?\s*:[^;{}]*?([0-9]*\.?[0-9]+)\s*(ms|s)", svg_text):
            number = float(value)
            durations.append(number if unit == "ms" else number * 1000)
        for value, unit in re.findall(r"animation-duration\s*:\s*([0-9]*\.?[0-9]+)\s*(ms|s)", svg_text):
            number = float(value)
            durations.append(number if unit == "ms" else number * 1000)
        return int(max(durations)) if durations else 3000

    def build_svg_capture_html(self, svg_text, capture_time_ms=0, scale=1.0):
        svg_text = re.sub(
            r"<svg\b",
            '<svg preserveAspectRatio="xMidYMid meet"',
            svg_text,
            count=1,
        )
        size = self.render_size
        return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
html, body {{
  width: {size}px;
  height: {size}px;
  margin: 0;
  overflow: hidden;
  background: transparent;
}}
body {{
  display: grid;
  place-items: center;
}}
.svg-wrap {{
  width: {size}px;
  height: {size}px;
  display: grid;
  place-items: center;
  transform: scale({scale});
  transform-origin: center center;
}}
svg {{
  width: {size}px !important;
  height: {size}px !important;
}}
*, *::before, *::after {{
  animation-play-state: paused !important;
  animation-delay: -{int(capture_time_ms)}ms !important;
}}
</style>
</head>
<body>
<div class="svg-wrap">
{svg_text}
</div>
</body>
</html>"""


class QtOctopusPet(QWidget):
    # Windows API 常量
    WM_HOTKEY = 0x0312
    MOD_NOREPEAT = 0x4000

    def __init__(self):
        super().__init__()
        self.app_dir = Path(__file__).resolve().parent
        self.drag_offset = QPoint()
        self.speech_bubble = None
        self.user_bubble = None
        self.is_continuous_mode = False
        self.screenshot_thread = None
        self.hotkey_ids = {}  # 存储注册的快捷键ID
        self.animator = None
        self.pending_reply_emotion = None
        self.chat_window = None
        self.pending_message = None  # 暂存待确认的消息
        self.signals = ConversationSignals()
        self.signals.reply_ready.connect(self.on_reply_ready)
        self.signals.error_ready.connect(self.on_error_ready)
        self.signals.status_ready.connect(self.on_status_ready)
        self.signals.toggle_continuous_screenshot_requested.connect(self.toggle_continuous_screenshot)
        self.signals.single_screenshot_requested.connect(self.take_single_screenshot)

        self.load_services()
        self.create_window()
        self.load_chat_history()
        self.setup_hotkey()

    def load_services(self):
        config_path = self.app_dir / "config.json"
        self.config = load_config_file(config_path)
        validate_config(self.config, config_path)
        self.api_key_env = self.config.get("api_key_env", "CLAUDE_API_KEY")
        self.api_key = os.environ.get(self.api_key_env, "")

        # Support environment variable for API base URL
        api_base_url_env = self.config.get("api_base_url_env")
        if api_base_url_env:
            self.config["api_base_url"] = os.environ.get(api_base_url_env, self.config.get("api_base_url", "https://api.anthropic.com"))

        self.notes_root = get_notes_root(self.app_dir)
        self.logger = setup_logging(self.notes_root)
        self.logger.info("小爪子启动")
        self.chat_log_store = ChatLogStore(
            self.notes_root,
            enabled=self.config.get("save_chat_logs", True),
        )
        self.note_store = MarkdownNoteStore(self.notes_root)
        self.note_action_handler = PetNoteActionHandler(self.note_store)
        self.claude_client = ClaudeClient(self.config, self.api_key)
        self.conversation_service = ConversationService(
            self.claude_client,
            self.note_action_handler,
            api_key_env=self.api_key_env,
            api_key=self.api_key,
        )
        self.screenshot_service = ScreenshotService(self.config)

        autobiography, recent_diary = load_diary_files(self.config)
        self.conversation_service.update_memory(autobiography, recent_diary)

    def create_window(self):
        window_title = get_ui_config(self.config, 'text', 'window_title', default="Clawd")
        self.setWindowTitle(window_title)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # 从配置读取窗口尺寸
        main_width = get_ui_config(self.config, 'window', 'main_width', default=420)
        main_height = get_ui_config(self.config, 'window', 'main_height', default=230)
        self.setFixedSize(main_width, main_height)

        pet_size = get_ui_config(self.config, 'pet', 'size', default=PET_SIZE)
        self.pet_label = QLabel(self)
        self.pet_label.setFixedSize(pet_size, pet_size)
        self.pet_label.setScaledContents(True)
        self.pet_label.move((self.width() - pet_size) // 2, 0)
        self.animator = PetAnimator(self.pet_label, self.app_dir, self.config)
        self.animator.set_steady("idle")

        input_bar_width = get_ui_config(self.config, 'pet', 'input_bar_width', default=370)
        self.input_bar = InputBar(self, self.config)
        self.input_bar.setFixedWidth(input_bar_width)
        self.input_bar.move((self.width() - self.input_bar.width()) // 2, pet_size + 10)

        self.history = HistoryDrawer(with_shadow=False)
        self.history.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.history.setAttribute(Qt.WA_TranslucentBackground, True)
        self.history.hide()
        self.chat_window = ChatWindow(config=self.config)
        self.chat_window.send_requested.connect(self.send_chat_window_message)
        self.chat_window.image_selected.connect(self.handle_image_upload)

        self.input_bar.close_button.clicked.connect(self.input_bar.hide)
        self.input_bar.history_button.clicked.connect(self.toggle_history)
        self.input_bar.chat_button.clicked.connect(self.toggle_chat_window)
        self.input_bar.send_button.clicked.connect(self.send_message)
        self.input_bar.entry.returnPressed.connect(self.send_message)
        self.pet_label.mousePressEvent = self.pet_mouse_press

        self.move_to_bottom_right()
        self.position_companion_windows()

    def load_chat_history(self):
        entries = self.chat_log_store.load_today_entries()
        records = [(role, message) for role, message, _timestamp, _thinking, _image_thumbnail in entries]
        for role, message, timestamp, thinking, image_thumbnail in entries:
            self.history.add_message(role, message, image_thumbnail=image_thumbnail)
            self.chat_window.add_message(role, message, self.time_label(timestamp), thinking=thinking, image_thumbnail=image_thumbnail)
        if self.config.get("load_today_chat_into_context", False):
            max_messages = int(self.config.get("chat_context_max_messages", 20))
            self.conversation_service.restore_history(records, max_messages=max_messages)
        self.position_companion_windows()

    def move_to_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        screen_margin = get_ui_config(self.config, 'window', 'screen_margin', default=20)
        x = screen.right() - self.width() - screen_margin
        y = screen.bottom() - self.height() - screen_margin
        self.move(x, y)

    def toggle_history(self):
        if self.history.isVisible():
            self.history.hide()
        else:
            self.position_companion_windows()
            self.history.show()

    def toggle_chat_window(self):
        if self.chat_window.isVisible():
            self.chat_window.hide()
            return
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()
        self.chat_window.focus_input()

    def append_chat(self, role, message, show_bubble=True, thinking=None, image_thumbnail=None):
        self.history.add_message(role, message, image_thumbnail=image_thumbnail)
        self.chat_window.add_message(role, message, self.current_time_label(), thinking=thinking, image_thumbnail=image_thumbnail)
        self.chat_log_store.append(role, message, thinking=thinking, image_thumbnail=image_thumbnail)
        if show_bubble:
            self.show_floating_bubble(role, message)

    def send_message(self):
        text = self.input_bar.entry.text().strip()
        if not text:
            return
        self.input_bar.entry.clear()
        self.send_text(text, source="pet_bar", show_bubble=True)

    def send_chat_window_message(self, text):
        self.send_text(text, source="chat_window", show_bubble=True)

    def handle_image_upload(self, image_path, text=""):
        """处理图片上传，可选附带文字"""
        from pet_core import process_image_for_upload

        # 从配置读取图片处理参数
        max_size_mb = get_ui_config(self.config, 'image_processing', 'max_upload_size_mb', default=5)
        thumbnail_size = get_ui_config(self.config, 'image_processing', 'thumbnail_size', default=150)

        # 处理图片
        image_base64, thumbnail_base64, error = process_image_for_upload(
            image_path,
            max_size_mb=max_size_mb,
            thumbnail_size=thumbnail_size
        )

        if error:
            # 显示错误消息
            self.show_error_with_retry(error, allow_retry=False)
            return

        # 使用用户输入的文字，如果为空则默认为 "[图片]"
        message_text = text.strip() if text.strip() else "[图片]"

        # 发送到API（带完整图片和缩略图）
        self.send_text(message_text, source="chat_window", show_bubble=True, image_base64=image_base64, image_thumbnail=thumbnail_base64)

    def send_text(self, text, source="pet_bar", show_bubble=True, image_base64=None, image_thumbnail=None):
        text = str(text).strip()
        if not text and not image_base64:
            return

        # 暂存消息，等成功后再保存到聊天记录文件
        self.pending_message = {
            "text": text,
            "image_base64": image_base64,
            "image_thumbnail": image_thumbnail,
            "source": source,
            "show_bubble": show_bubble
        }

        # 立即显示用户消息到聊天窗口（视觉反馈）
        if show_bubble and source == "chat_window":
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M")
            self.chat_window.add_message("user", text, timestamp, image_thumbnail=image_thumbnail)
            self.history.add_message("user", text, image_thumbnail=image_thumbnail)

        self.animator.mark_activity()
        self.set_chat_status("thinking")
        self.animator.set_steady("thinking")

        # 先显示用户消息（但不保存到聊天记录）
        if show_bubble:
            self.show_floating_bubble("user", text)

        threading.Thread(target=self.call_api_worker, args=(text, image_base64, source), daemon=True).start()

    def call_api_worker(self, text, image_base64=None, source="pet_bar"):
        try:
            result = self.conversation_service.send_message(text, image_base64)
            self.signals.reply_ready.emit(
                result["display_message"],
                result.get("emotion") or "",
                source,
                result.get("thinking") or ""
            )
        except MissingApiKeyError as exc:
            message = f"没有找到 API key。请设置环境变量 {exc.env_name} 后重启小爪子。"
            self.logger.error(f"API key 缺失: {exc.env_name}")
            self.signals.error_ready.emit(message, "missing_key", source)
        except requests.exceptions.ConnectionError as exc:
            safe_message = "连接被中断了。请稍后重试，或检查代理/网络是否刚刚切换。"
            self.logger.error(f"连接错误: {self.sanitize_error(exc)}")
            self.signals.error_ready.emit(safe_message, "network", source)
        except requests.exceptions.Timeout as exc:
            safe_message = "请求超时了。请稍后重试，或检查网络和代理。"
            self.logger.error(f"请求超时: {self.sanitize_error(exc)}")
            self.signals.error_ready.emit(safe_message, "network", source)
        except requests.exceptions.RequestException as exc:
            safe_message = f"网络请求失败：{self.sanitize_error(exc)}"
            self.logger.error(f"网络请求异常: {self.sanitize_error(exc)}")
            self.signals.error_ready.emit(safe_message, "network", source)
        except Exception as exc:
            safe_message = f"发生错误：{self.sanitize_error(exc)}"
            self.logger.error(f"未预期的错误: {self.sanitize_error(exc)}", exc_info=True)
            self.signals.error_ready.emit(safe_message, "error", source)

    def sanitize_error(self, error):
        """从错误消息中移除敏感信息"""
        message = str(error)
        if self.api_key:
            message = message.replace(self.api_key, "***")
        return message

    def on_reply_ready(self, message, emotion, source, thinking):
        self.animator.mark_activity()
        self.set_chat_status("typing")
        self.animator.set_steady("typing")
        self.pending_reply_emotion = emotion or "happy"
        self.pending_reply_source = source

        # 成功了！现在保存用户消息到聊天记录文件
        if self.pending_message:
            user_text = self.pending_message["text"]
            image_thumbnail = self.pending_message.get("image_thumbnail")

            # 保存到聊天记录文件（不显示 bubble，因为已经在 send_text 中显示了）
            self.chat_log_store.append("user", user_text, image_thumbnail=image_thumbnail)

            # 清空暂存
            self.pending_message = None

        # 保存助手回复
        self.append_chat("assistant", message, show_bubble=source != "chat_window", thinking=thinking)
        reply_delay = get_ui_config(self.config, 'animations', 'reply_animation_delay_ms', default=650)
        QTimer.singleShot(reply_delay, self.finish_reply_animation)

    def on_error_ready(self, message, _kind, source):
        self.animator.mark_activity()
        self.set_chat_status("error")
        self.animator.set_steady("idle_reading" if self.is_continuous_mode else "idle")
        self.animator.play_error()

        # 截图失败：只显示错误提示，不提供重试（5秒后会自动再截）
        if source == "screenshot":
            self.show_floating_bubble("assistant", f"📷 截图发送失败\n\n{message}")
        else:
            # 手动输入失败：显示重试按钮
            self.show_error_with_retry(message, source)

    def on_status_ready(self, message, state):
        self.animator.mark_activity()
        self.set_chat_status(state)
        if state == "thinking":
            self.animator.set_steady("thinking")
        elif state == "typing":
            self.animator.set_steady("typing")
        elif state == "error":
            self.animator.play_error()
        elif state == "idle":
            self.animator.set_steady("idle_reading" if self.is_continuous_mode else "idle")
        if message:
            self.show_floating_bubble("assistant", message)

    def finish_reply_animation(self):
        self.set_chat_status("idle")
        emotion = self.pending_reply_emotion or "happy"
        self.pending_reply_emotion = None
        self.animator.set_steady("idle_reading" if self.is_continuous_mode else "idle")
        happy_duration = get_ui_config(self.config, 'animations', 'reaction_happy_ms', default=3200)
        self.animator.play_reaction(emotion, duration=happy_duration, fallback="happy")

    def setup_hotkey(self):
        """使用 Windows API 注册全局快捷键"""
        single_hotkey = self.screenshot_service.get_single_hotkey_name()
        continuous_hotkey = self.screenshot_service.get_continuous_hotkey_name()

        # 注册单次截图快捷键
        single_vk, single_mod = self.parse_hotkey(single_hotkey)
        if single_vk:
            hotkey_id = 1
            if ctypes.windll.user32.RegisterHotKey(int(self.winId()), hotkey_id, single_mod, single_vk):
                self.hotkey_ids[hotkey_id] = 'single'
                self.logger.info(f"已注册单次截图快捷键: {single_hotkey}")
            else:
                self.logger.error(f"注册单次截图快捷键失败: {single_hotkey}")

        # 注册连续截图快捷键
        continuous_vk, continuous_mod = self.parse_hotkey(continuous_hotkey)
        if continuous_vk:
            hotkey_id = 2
            if ctypes.windll.user32.RegisterHotKey(int(self.winId()), hotkey_id, continuous_mod, continuous_vk):
                self.hotkey_ids[hotkey_id] = 'continuous'
                self.logger.info(f"已注册连续截图快捷键: {continuous_hotkey}")
            else:
                self.logger.error(f"注册连续截图快捷键失败: {continuous_hotkey}")

    def parse_hotkey(self, hotkey_str):
        """解析快捷键字符串，返回 (virtual_key, modifiers)"""
        # Virtual Key Codes (常用的)
        vk_map = {
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73,
            'f5': 0x74, 'f6': 0x75, 'f7': 0x76, 'f8': 0x77,
            'f9': 0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
            'a': 0x41, 'b': 0x42, 'c': 0x43, 'd': 0x44,
            'e': 0x45, 'f': 0x46, 'g': 0x47, 'h': 0x48,
            'i': 0x49, 'j': 0x4A, 'k': 0x4B, 'l': 0x4C,
            'm': 0x4D, 'n': 0x4E, 'o': 0x4F, 'p': 0x50,
            'q': 0x51, 'r': 0x52, 's': 0x53, 't': 0x54,
            'u': 0x55, 'v': 0x56, 'w': 0x57, 'x': 0x58,
            'y': 0x59, 'z': 0x5A,
            '0': 0x30, '1': 0x31, '2': 0x32, '3': 0x33,
            '4': 0x34, '5': 0x35, '6': 0x36, '7': 0x37,
            '8': 0x38, '9': 0x39,
            # 鼠标按键
            'mouse4': 0x05,  # 鼠标侧键（前进键）
            'mouse5': 0x06,  # 鼠标侧键（后退键）
            'xbutton1': 0x05,  # 同 mouse4
            'xbutton2': 0x06,  # 同 mouse5
        }

        # Modifier keys
        MOD_ALT = 0x0001
        MOD_CONTROL = 0x0002
        MOD_SHIFT = 0x0004
        MOD_WIN = 0x0008

        parts = [p.strip().lower() for p in hotkey_str.split('+')]
        modifiers = self.MOD_NOREPEAT  # 防止重复触发

        vk_code = None
        for part in parts:
            if part == 'ctrl' or part == 'control':
                modifiers |= MOD_CONTROL
            elif part == 'shift':
                modifiers |= MOD_SHIFT
            elif part == 'alt':
                modifiers |= MOD_ALT
            elif part == 'win':
                modifiers |= MOD_WIN
            elif part in vk_map:
                vk_code = vk_map[part]

        return vk_code, modifiers

    def nativeEvent(self, eventType, message):
        """接收 Windows 消息，处理热键"""
        if eventType == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(int(message))
            if msg.message == self.WM_HOTKEY:
                hotkey_id = msg.wParam
                action = self.hotkey_ids.get(hotkey_id)
                if action == 'single':
                    self.signals.single_screenshot_requested.emit()
                elif action == 'continuous':
                    self.signals.toggle_continuous_screenshot_requested.emit()
                return True, 0
        return super().nativeEvent(eventType, message)

    def toggle_continuous_screenshot(self):
        self.animator.mark_activity()
        self.is_continuous_mode = not self.is_continuous_mode
        notification_duration = get_ui_config(self.config, 'animations', 'reaction_notification_ms', default=1500)

        if self.is_continuous_mode:
            self.set_chat_status("thinking")
            self.animator.set_steady("idle_reading")
            self.animator.play_reaction("notification", duration=notification_duration)
            self.show_floating_bubble("assistant", "连续截图模式已开启")
            self.input_bar.eye_indicator.set_open(True)
            self.screenshot_thread = threading.Thread(target=self.continuous_screenshot, daemon=True)
            self.screenshot_thread.start()
        else:
            self.set_chat_status("idle")
            self.animator.set_steady("idle")
            self.animator.play_reaction("sleeping", duration=notification_duration)
            self.show_floating_bubble("assistant", "连续截图模式已关闭")
            self.input_bar.eye_indicator.set_open(False)

    def continuous_screenshot(self):
        while self.is_continuous_mode:
            self.take_screenshot()
            time.sleep(self.config.get("screenshot_interval", 5))

    def take_single_screenshot(self):
        """单次截图：发一张就停"""
        self.animator.mark_activity()
        notification_duration = get_ui_config(self.config, 'animations', 'reaction_notification_ms', default=1500)
        self.animator.play_reaction("notification", duration=int(notification_duration * 0.53))
        self.take_screenshot()

    def take_screenshot(self):
        image_base64, status = self.screenshot_service.capture_png_base64()
        if status == "no_whitelist_match":
            self.signals.status_ready.emit("未找到白名单窗口", "error")
            return
        if status == "foreground_not_whitelisted":
            self.signals.status_ready.emit("前台窗口不在白名单", "error")
            return
        self.signals.status_ready.emit("截图已发送", "thinking")
        screenshot_message = get_ui_config(self.config, 'text', 'screenshot_message', default="这是宝宝发送过来的截图。")
        # 截图不走 send_text，直接调用 call_api_worker（不支持重试）
        threading.Thread(target=self.call_api_worker, args=(screenshot_message, image_base64, "screenshot"), daemon=True).start()

    def show_floating_bubble(self, role, message):
        user_bubble_display_ms = get_ui_config(self.config, 'animations', 'user_bubble_display_ms', default=6000)
        assistant_bubble_display_ms = get_ui_config(self.config, 'animations', 'assistant_bubble_display_ms', default=18000)

        if role == "user":
            if self.user_bubble:
                self.user_bubble.close()
            self.user_bubble = FloatingBubble(role, message)
            self.user_bubble.show()
            QTimer.singleShot(user_bubble_display_ms, self.hide_user_bubble)
        else:
            if self.speech_bubble:
                self.speech_bubble.close()
            self.speech_bubble = FloatingBubble(role, message)
            self.speech_bubble.show()
            QTimer.singleShot(assistant_bubble_display_ms, self.hide_speech_bubble)
        self.position_companion_windows()

    def hide_user_bubble(self):
        if self.user_bubble:
            self.user_bubble.close()
            self.user_bubble = None

    def hide_speech_bubble(self):
        if self.speech_bubble:
            self.speech_bubble.close()
            self.speech_bubble = None

    def show_error_with_retry(self, message, source):
        """显示带重试/取消按钮的错误气泡"""
        if self.speech_bubble:
            self.speech_bubble.close()

        self.speech_bubble = ErrorBubbleWithRetry(message)
        self.speech_bubble.retry_clicked.connect(self.retry_last_message)
        self.speech_bubble.cancel_clicked.connect(self.cancel_pending_message)
        self.speech_bubble.show()
        self.position_companion_windows()

    def retry_last_message(self):
        """重试上一条失败的消息"""
        if not self.pending_message:
            return

        self.logger.info("用户点击重试")
        if self.speech_bubble:
            self.speech_bubble.close()
            self.speech_bubble = None

        # 取出暂存的消息
        text = self.pending_message["text"]
        image_base64 = self.pending_message.get("image_base64")
        source = self.pending_message["source"]

        # 设置状态
        self.animator.mark_activity()
        self.set_chat_status("thinking")

        # 直接调用 API（不通过 send_text，避免重复显示用户消息）
        threading.Thread(target=self.call_api_worker, args=(text, image_base64, source), daemon=True).start()

    def cancel_pending_message(self):
        """取消待重试的消息"""
        self.logger.info("用户取消重试")

        # 如果消息已经显示在聊天窗口，需要删除最后一条用户消息
        if self.pending_message and self.pending_message.get("source") == "chat_window":
            # 从聊天窗口删除最后一条消息（如果是用户消息）
            if self.chat_window.messages and self.chat_window.messages[-1][0] == "user":
                self.chat_window.messages.pop()
                # 重建界面
                self.chat_window.rebuild_messages()

            # 从历史抽屉删除最后一条消息（如果是用户消息）
            # HistoryDrawer 没有保存消息列表，所以无法删除，但这不影响主要功能

        self.pending_message = None

        if self.speech_bubble:
            self.speech_bubble.close()
            self.speech_bubble = None

        self.set_chat_status("idle")
        self.animator.set_steady("idle_reading" if self.is_continuous_mode else "idle")

    def set_chat_status(self, state):
        self.input_bar.status_dot.set_state(state)
        self.chat_window.set_status(state)

    def current_time_label(self):
        return time.strftime("%H:%M")

    def time_label(self, timestamp):
        return str(timestamp or self.current_time_label())[:5]

    def position_companion_windows(self):
        screen = QApplication.primaryScreen().availableGeometry()
        margin = WINDOW_MARGIN
        pet_rect = QRect(
            self.x() + self.pet_label.x(),
            self.y() + self.pet_label.y(),
            self.pet_label.width(),
            self.pet_label.height(),
        )
        input_rect = QRect(
            self.x() + self.input_bar.x(),
            self.y() + self.input_bar.y(),
            self.input_bar.width(),
            self.input_bar.height(),
        )

        def clamp(value, low, high):
            return max(low, min(value, high))

        def move_near_pet(widget, preferred_side="below", min_width=0, min_height=0, obstacles=None):
            if not widget:
                return None
            widget.adjustSize()
            width = max(min_width, widget.width())
            height = max(min_height, widget.height())
            x = clamp(
                pet_rect.center().x() - width // 2,
                screen.left() + margin,
                screen.right() - width - margin,
            )
            if preferred_side == "above":
                y_candidates = [
                    pet_rect.top() - height - PET_WINDOW_GAP,
                    pet_rect.bottom() + PET_WINDOW_GAP,
                ]
            else:
                y_candidates = [
                    pet_rect.bottom() + PET_WINDOW_GAP,
                    pet_rect.top() - height - PET_WINDOW_GAP,
                ]

            for rect in obstacles or []:
                if rect.top() < pet_rect.top():
                    y_candidates.extend([rect.bottom() + BUBBLE_GAP, rect.top() - height - BUBBLE_GAP])
                else:
                    y_candidates.extend([rect.top() - height - BUBBLE_GAP, rect.bottom() + BUBBLE_GAP])

            y = y_candidates[0]
            for candidate_y in y_candidates:
                candidate = QRect(x, candidate_y, width, height)
                if (
                    candidate_y >= screen.top() + margin
                    and candidate_y + height <= screen.bottom() - margin
                    and not any(candidate.intersects(rect) for rect in obstacles or [])
                ):
                    y = candidate_y
                    break
            y = clamp(y, screen.top() + margin, screen.bottom() - height - margin)
            if widget is self.history:
                widget.resize(width, height)
            widget.move(x, y)
            return QRect(x, y, width, height)

        user_rect = None
        if self.user_bubble:
            user_rect = move_near_pet(
                self.user_bubble,
                preferred_side="below",
                min_width=USER_BUBBLE_MIN_WIDTH,
                min_height=USER_BUBBLE_MIN_HEIGHT,
                obstacles=[input_rect],
            )

        speech_obstacles = [input_rect]
        if user_rect:
            speech_obstacles.append(user_rect)
        if self.speech_bubble:
            speech_rect = move_near_pet(
                self.speech_bubble,
                preferred_side="above",
                min_width=ASSISTANT_BUBBLE_MIN_WIDTH,
                min_height=ASSISTANT_BUBBLE_MIN_HEIGHT,
                obstacles=speech_obstacles,
            )
        else:
            speech_rect = None

        if self.history:
            self.history.adjustSize()
            width = self.history.width()
            height = self.history.height()
            x = pet_rect.right() + HISTORY_WINDOW_PET_GAP
            if x + width > screen.right() - margin:
                x = pet_rect.left() - width - HISTORY_WINDOW_PET_GAP
            x = clamp(x, screen.left() + margin, screen.right() - width - margin)

            obstacles = [rect for rect in (input_rect, user_rect, speech_rect) if rect]
            y_candidates = [
                pet_rect.top() - 120,
                pet_rect.bottom() + PET_WINDOW_GAP,
                pet_rect.top() - height - PET_WINDOW_GAP,
            ]
            for rect in obstacles:
                y_candidates.extend([
                    rect.bottom() + BUBBLE_GAP,
                    rect.top() - height - BUBBLE_GAP,
                ])

            y = y_candidates[0]
            for candidate_y in y_candidates:
                candidate = QRect(x, candidate_y, width, height)
                if (
                    candidate_y >= screen.top() + margin
                    and candidate_y + height <= screen.bottom() - margin
                    and not any(candidate.intersects(rect) for rect in obstacles)
                ):
                    y = candidate_y
                    break
            y = clamp(y, screen.top() + margin, screen.bottom() - height - margin)
            self.history.move(x, y)

    def pet_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.animator.mark_activity()
            self.input_bar.setVisible(not self.input_bar.isVisible())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.animator.mark_activity()
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            self.position_companion_windows()
            event.accept()

    def closeEvent(self, event):
        self.is_continuous_mode = False
        # 注销所有注册的全局快捷键
        for hotkey_id in self.hotkey_ids.keys():
            ctypes.windll.user32.UnregisterHotKey(int(self.winId()), hotkey_id)
        self.logger.info("已注销所有快捷键")
        for widget in (self.history, self.chat_window, self.user_bubble, self.speech_bubble):
            if widget:
                widget.close()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    # 检查是否需要运行首次配置向导
    app_dir = Path(__file__).resolve().parent
    config_path = app_dir / "config.json"

    if not config_path.exists():
        from setup_wizard import run_wizard
        success = run_wizard(app_dir)
        if not success:
            # 用户取消了配置，退出程序
            sys.exit(0)

    window = QtOctopusPet()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
