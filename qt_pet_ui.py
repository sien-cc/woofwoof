"""Reusable PySide6 UI widgets for the desktop pet."""

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QIcon, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QDialog,
)

from pet_ui import (
    ACCENT,
    ASSISTANT_BUBBLE,
    ASSISTANT_BUBBLE_OUTLINE,
    BUBBLE_TEXT,
    HISTORY_BUBBLE_MAX_WIDTH,
    INPUT_BG,
    INPUT_BORDER,
    INPUT_PANEL_BG,
    INPUT_TEXT,
    THEME_DARK,
    THEME_LIGHT,
    USER_BUBBLE,
    USER_BUBBLE_OUTLINE,
)


def rgba(hex_color, alpha):
    color = QColor(hex_color)
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {alpha})"


def add_shadow(widget, blur=18, y=6, alpha=45):
    shadow = QGraphicsDropShadowEffect(widget)
    shadow.setBlurRadius(blur)
    shadow.setOffset(0, y)
    shadow.setColor(QColor(69, 39, 24, alpha))
    widget.setGraphicsEffect(shadow)


class StatusDot(QFrame):
    COLORS = {
        "idle": "#83b77a",
        "thinking": "#e6b75f",
        "typing": ACCENT,
        "error": "#cf6b68",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(10, 10)
        self.set_state("idle")

    def set_state(self, state):
        color = self.COLORS.get(state, self.COLORS["idle"])
        self.setStyleSheet(
            f"""
            StatusDot {{
                background: {color};
                border: 1px solid {rgba("#ffffff", 180)};
                border-radius: 5px;
            }}
            """
        )


class EyeIndicator(QFrame):
    """眼睛指示器：闭眼=截图关闭，睁眼=连续截图中"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.is_open = False

    def set_open(self, is_open):
        """设置眼睛状态：True=睁眼，False=闭眼"""
        self.is_open = is_open
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = QColor(INPUT_BG)
        color.setAlpha(205)
        painter.setPen(QPen(color, 2.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)

        center_x = 10
        center_y = 10

        if self.is_open:
            # 睁眼：画椭圆 + 瞳孔
            painter.drawEllipse(QPointF(center_x, center_y), 7, 5)
            painter.setBrush(QColor(INPUT_BG))
            painter.drawEllipse(QPointF(center_x, center_y), 2.5, 2.5)
        else:
            # 闭眼：弧形眼皮 + 三根睫毛
            # 下弧线（眼皮）
            painter.drawArc(3, 3, 14, 10, 180 * 16, 180 * 16)

            # 三根睫毛（从弧线向下延伸的小竖线）
            # 左侧睫毛
            painter.drawLine(QPointF(5, 12), QPointF(4, 15))
            # 中间睫毛
            painter.drawLine(QPointF(10, 13), QPointF(10, 16))
            # 右侧睫毛
            painter.drawLine(QPointF(15, 12), QPointF(16, 15))


class IconGlassButton(QPushButton):
    def __init__(self, icon_name, parent=None):
        super().__init__(parent)
        self.icon_name = icon_name
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 34)
        self.setFlat(True)
        self.setStyleSheet("QPushButton { border: none; background: transparent; }")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        icon = QColor(INPUT_BG)
        if self.isDown():
            icon.setAlpha(250)
        elif self.underMouse():
            icon.setAlpha(230)
        else:
            icon.setAlpha(205)

        painter.setPen(QPen(icon, 2.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        if self.icon_name == "history":
            self.draw_page_icon(painter)
        elif self.icon_name == "chat":
            self.draw_chat_icon(painter)
        elif self.icon_name == "send":
            self.draw_send_icon(painter)

    def draw_page_icon(self, painter):
        path = QPainterPath()
        path.moveTo(15, 9)
        path.lineTo(24, 9)
        path.lineTo(29, 14)
        path.lineTo(29, 25)
        path.lineTo(15, 25)
        path.closeSubpath()
        painter.drawPath(path)
        painter.drawLine(QPointF(24, 9), QPointF(24, 14))
        painter.drawLine(QPointF(24, 14), QPointF(29, 14))
        painter.drawLine(QPointF(18, 18), QPointF(26, 18))
        painter.drawLine(QPointF(18, 22), QPointF(24, 22))

    def draw_send_icon(self, painter):
        path = QPainterPath()
        path.moveTo(12, 11)
        path.lineTo(31, 17)
        path.lineTo(12, 23)
        path.lineTo(16, 18)
        path.lineTo(23, 17)
        path.lineTo(16, 16)
        path.closeSubpath()
        painter.drawPath(path)

    def draw_chat_icon(self, painter):
        painter.drawRoundedRect(12, 10, 18, 14, 3, 3)
        painter.drawLine(QPointF(17, 24), QPointF(14, 28))
        painter.drawLine(QPointF(17, 24), QPointF(20, 24))
        painter.drawLine(QPointF(16, 15), QPointF(26, 15))
        painter.drawLine(QPointF(16, 19), QPointF(23, 19))


class ThemeToggleButton(QPushButton):
    """主题切换按钮（日/夜模式）"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dark = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(28, 28)
        self.update_style()

    def update_style(self):
        emoji = "🌙" if not self.is_dark else "☀️"
        self.setText(emoji)
        self.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border-radius: 14px;
            }
            """
        )

    def toggle(self):
        self.is_dark = not self.is_dark
        self.update_style()


class EmojiPicker(QFrame):
    """Emoji 选择器弹出面板"""
    emoji_selected = Signal(str)

    COMMON_EMOJIS = [
        # 笑脸
        "😊", "😂", "🥰", "😍", "🤗", "😭", "😢", "😅", "😎", "🤔",
        # 手势
        "👍", "👎", "👌", "✌️", "🙏", "👏", "🤝", "💪",
        # 表情
        "😴", "🥱", "😱", "😤", "🥺", "😳", "🤨", "😏",
        # 动物
        "🐱", "🐶", "🐻", "🐰", "🦊", "🐼", "🐙", "🦀",
        # 其他
        "❤️", "💕", "✨", "🎉", "🔥", "💯", "⭐", "🌟",
    ]

    def __init__(self, parent=None, is_dark=False):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.is_dark = is_dark

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # 创建 emoji 网格
        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(2)

        # 每行 10 个 emoji，按钮高度增加到 38px
        for i, emoji in enumerate(self.COMMON_EMOJIS):
            if i % 10 == 0 and i > 0:
                layout.addWidget(grid)
                grid = QWidget()
                grid_layout = QHBoxLayout(grid)
                grid_layout.setContentsMargins(0, 0, 0, 0)
                grid_layout.setSpacing(2)

            btn = QPushButton(emoji)
            btn.setFixedSize(32, 38)  # 增加高度，避免 emoji 被切割
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, e=emoji: self.select_emoji(e))
            grid_layout.addWidget(btn)

        layout.addWidget(grid)
        self.setFixedSize(360, 190)  # 增加高度以适应更高的按钮
        self.apply_theme(is_dark)

    def apply_theme(self, is_dark):
        """应用主题样式"""
        self.is_dark = is_dark
        if is_dark:
            bg_color = "#2d2d2d"
            border_color = "#555"
            hover_color = "#3e3e3e"
        else:
            bg_color = "white"
            border_color = "#ccc"
            hover_color = "#f0f0f0"

        self.setStyleSheet(
            f"""
            EmojiPicker {{
                background: {bg_color};
                border: 1px solid {border_color};
                border-radius: 8px;
            }}
            QPushButton {{
                background: transparent;
                border: none;
                font-size: 24px;
                padding: 0px;
            }}
            QPushButton:hover {{
                background: {hover_color};
                border-radius: 4px;
            }}
            """
        )

    def select_emoji(self, emoji):
        self.emoji_selected.emit(emoji)
        self.hide()


class EmojiButton(QPushButton):
    """Emoji 按钮（点击打开选择器）"""
    def __init__(self, parent=None):
        super().__init__("😊", parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(32, 32)
        self.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: 1px solid rgba(0, 0, 0, 0.1);
                border-radius: 4px;
                font-size: 18px;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.05);
                border: 1px solid rgba(0, 0, 0, 0.2);
            }
            """
        )
        self.picker = EmojiPicker(self)


class ChatBubble(QFrame):
    def __init__(self, text, role="assistant", parent=None, image_thumbnail=None):
        super().__init__(parent)
        self.setObjectName("chatBubble")
        self.setAttribute(Qt.WA_StyledBackground, True)
        is_user = role == "user"
        bg = USER_BUBBLE if is_user else ASSISTANT_BUBBLE
        border = USER_BUBBLE_OUTLINE if is_user else ASSISTANT_BUBBLE_OUTLINE
        self.setMaximumWidth(HISTORY_BUBBLE_MAX_WIDTH)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Minimum)
        self.setStyleSheet(
            f"""
            QFrame#chatBubble {{
                background: {rgba(bg, 224)};
                border: 1px solid {border};
                border-radius: 15px;
            }}
            QLabel {{
                color: {BUBBLE_TEXT};
                font: 10pt "Microsoft YaHei UI";
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(13, 9, 13, 9)

        # 如果有图片缩略图，先显示图片
        if image_thumbnail:
            import base64
            from PySide6.QtGui import QPixmap
            image_data = base64.b64decode(image_thumbnail)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setScaledContents(False)
            image_label.setCursor(Qt.PointingHandCursor)
            image_label.setToolTip("点击查看原图")
            # 存储缩略图数据，供点击放大使用
            image_label.image_thumbnail = image_thumbnail
            image_label.mousePressEvent = lambda e: self.show_full_image(image_thumbnail)
            layout.addWidget(image_label)

        label = QLabel(str(text))
        label.setWordWrap(True)
        label.setMaximumWidth(HISTORY_BUBBLE_MAX_WIDTH - 28)
        layout.addWidget(label)

    def show_full_image(self, image_thumbnail):
        """点击缩略图时显示原图（暂时先显示缩略图，后面会改成原图）"""
        # 这里先简单弹出一个对话框显示图片
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        from PySide6.QtGui import QPixmap
        import base64

        dialog = QDialog(self)
        dialog.setWindowTitle("查看图片")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        image_data = base64.b64decode(image_thumbnail)
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)

        dialog.exec()


class HistoryDrawer(QFrame):
    def __init__(self, parent=None, with_shadow=True):
        super().__init__(parent)
        self.setObjectName("historyDrawer")
        self.setFixedWidth(390)
        self.setMinimumHeight(260)
        self.setMaximumHeight(460)
        self.setStyleSheet(
            f"""
            QLabel#title {{
                color: {INPUT_TEXT};
                font: 700 10pt "Microsoft YaHei UI";
            }}
            """
        )
        if with_shadow:
            add_shadow(self, blur=24, y=8, alpha=58)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("聊天记录")
        title.setObjectName("title")
        close_btn = QPushButton("×")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            f"""
            QPushButton {{
                color: {rgba(INPUT_TEXT, 210)};
                background: transparent;
                border: none;
                font: 700 12pt "Microsoft YaHei UI";
            }}
            QPushButton:hover {{
                background: {rgba(INPUT_BORDER, 88)};
                border-radius: 14px;
            }}
            """
        )
        close_btn.clicked.connect(self.hide)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_btn)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.scroll.viewport().setStyleSheet("background: transparent;")
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(8)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)

        bg = QColor(INPUT_PANEL_BG)
        bg.setAlpha(238)
        border = QColor(INPUT_BORDER)
        border.setAlpha(232)

        painter.setBrush(bg)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(rect, 18, 18)

    def add_message(self, role, text, image_thumbnail=None):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        bubble = ChatBubble(text, role=role, image_thumbnail=image_thumbnail)
        if role == "user":
            row.addStretch(1)
            row.addWidget(bubble)
        else:
            row.addWidget(bubble)
            row.addStretch(1)
        self.body_layout.insertLayout(self.body_layout.count() - 1, row)
        QTimer.singleShot(
            0,
            lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            ),
        )


class ThinkingBlock(QFrame):
    """可折叠的思维链显示组件"""
    def __init__(self, thinking_text, is_dark=False, parent=None):
        super().__init__(parent)
        self.thinking_text = thinking_text
        self.is_dark = is_dark
        self.is_expanded = False

        self.setObjectName("thinkingBlock")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        # 折叠/展开按钮
        self.toggle_button = QPushButton("▶ 偷看小爪子的脑子")
        self.toggle_button.setCursor(Qt.PointingHandCursor)
        self.toggle_button.clicked.connect(self.toggle_expand)
        layout.addWidget(self.toggle_button)

        # 思维链内容（初始隐藏）
        self.content_widget = QTextBrowser()
        self.content_widget.setOpenExternalLinks(False)
        self.content_widget.setReadOnly(True)
        self.content_widget.setFrameShape(QFrame.NoFrame)
        self.content_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.content_widget.document().setDocumentMargin(8)
        self.content_widget.setMarkdown(thinking_text)
        self.content_widget.setVisible(False)
        self.content_widget.document().contentsChanged.connect(self.adjust_content_height)
        layout.addWidget(self.content_widget)

        self.apply_theme(is_dark)

    def apply_theme(self, is_dark):
        """应用主题样式"""
        self.is_dark = is_dark
        if is_dark:
            btn_bg = "#2d2d2d"
            btn_text = "#888888"
            btn_hover = "#3e3e3e"
            content_bg = "#1a1a1a"
            content_text = "#888888"
            content_border = "#444444"
        else:
            btn_bg = "#f5f5f5"
            btn_text = "#666666"
            btn_hover = "#e8e8e8"
            content_bg = "#fafafa"
            content_text = "#666666"
            content_border = "#dddddd"

        self.setStyleSheet(
            f"""
            QFrame#thinkingBlock {{
                background: transparent;
                border: none;
            }}
            QPushButton {{
                color: {btn_text};
                background: {btn_bg};
                border: 1px solid {content_border};
                border-radius: 4px;
                padding: 4px 8px;
                text-align: left;
                font: 9pt "Microsoft YaHei UI";
            }}
            QPushButton:hover {{
                background: {btn_hover};
            }}
            QTextBrowser {{
                color: {content_text};
                background: {content_bg};
                border: 1px solid {content_border};
                border-radius: 4px;
                font: 9pt "Microsoft YaHei UI", "Consolas";
            }}
            """
        )

    def toggle_expand(self):
        """切换展开/折叠状态"""
        self.is_expanded = not self.is_expanded
        if self.is_expanded:
            self.toggle_button.setText("▼ 你这个罪人！")
            self.content_widget.setVisible(True)
            self.adjust_content_height()
        else:
            self.toggle_button.setText("▶ 偷看小爪子的脑子")
            self.content_widget.setVisible(False)

    def adjust_content_height(self):
        """调整内容高度"""
        if self.is_expanded and self.content_widget.isVisible():
            width = max(1, self.content_widget.viewport().width())
            self.content_widget.document().setTextWidth(width)
            self.content_widget.setFixedHeight(int(self.content_widget.document().size().height()) + 20)


class ChatTextEdit(QTextEdit):
    send_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 禁用拖拽到输入框（让父窗口处理）
        self.setAcceptDrops(False)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not event.modifiers() & Qt.ShiftModifier:
            self.send_requested.emit()
            return
        super().keyPressEvent(event)


class TranscriptMessage(QFrame):
    @staticmethod
    def get_role_labels(config=None):
        """从配置获取角色名称"""
        from pet_core import get_ui_config
        user_name = get_ui_config(config, 'text', 'user_name', default="你")
        pet_name = get_ui_config(config, 'text', 'pet_name', default="小爪子")
        return {
            "user": user_name,
            "assistant": pet_name,
        }

    ROLE_LABELS = {
        "user": "你",
        "assistant": "小爪子",
    }

    def __init__(self, role, text, timestamp, parent=None, theme=None, thinking=None, image_thumbnail=None, config=None):
        super().__init__(parent)
        self.setObjectName("transcriptMessage")
        self.role = role
        self.thinking = thinking  # 保存 thinking 用于主题切换
        self.image_thumbnail = image_thumbnail  # 保存 image_thumbnail 用于主题切换

        # 使用传入的主题或默认主题
        if theme is None:
            theme = THEME_LIGHT

        role_color = theme['user_role'] if role == 'user' else theme['assistant_role']

        # 从配置获取角色名称（如果可用）
        role_labels = self.get_role_labels(config) if config else self.ROLE_LABELS
        role_label_text = role_labels.get(role, role)

        self.setStyleSheet(
            f"""
            QFrame#transcriptMessage {{
                background: transparent;
                border: none;
            }}
            QLabel#timestamp {{
                color: {rgba(theme['timestamp'], theme['timestamp_alpha'])};
                font: 9pt "Consolas", "Microsoft YaHei UI", "Segoe UI Emoji";
            }}
            QLabel#roleName {{
                color: {role_color};
                font: 700 9pt "Microsoft YaHei UI", "Segoe UI Emoji";
            }}
            QTextBrowser {{
                color: {theme['text']};
                background: transparent;
                border: none;
                font: 10pt "Microsoft YaHei UI", "Segoe UI Emoji";
            }}
            """
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 3, 8, 3)
        layout.setSpacing(2)

        # 第一行：时间戳 + 角色名
        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)

        timestamp_label = QLabel(f"[{timestamp}]")
        timestamp_label.setObjectName("timestamp")

        role_name_label = QLabel(role_label_text)
        role_name_label.setObjectName("roleName")

        meta_row.addWidget(timestamp_label)
        meta_row.addWidget(role_name_label)
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        # 如果有思维链，显示思维链组件（仅助手消息）
        self.thinking_block = None
        if thinking and role == 'assistant':
            is_dark = theme.get('name') == 'dark'
            self.thinking_block = ThinkingBlock(thinking, is_dark=is_dark)
            layout.addWidget(self.thinking_block)

        # 如果有图片缩略图，显示缩略图
        if image_thumbnail:
            import base64
            image_data = base64.b64decode(image_thumbnail)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data)

            image_label = QLabel()
            image_label.setPixmap(pixmap)
            image_label.setCursor(Qt.PointingHandCursor)
            image_label.setToolTip("点击查看原图")
            image_label.mousePressEvent = lambda e: self.show_full_image(image_thumbnail)
            layout.addWidget(image_label)

        # 第二行：消息内容
        body = QTextBrowser()
        body.setOpenExternalLinks(False)
        body.setReadOnly(True)
        body.setFrameShape(QFrame.NoFrame)
        body.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        body.document().setDocumentMargin(0)
        body.setMarkdown(str(text))
        body.setMinimumHeight(1)
        body.document().contentsChanged.connect(lambda: self.adjust_body_height(body))
        self.adjust_body_height(body)
        layout.addWidget(body)

    def adjust_body_height(self, body):
        width = max(1, body.viewport().width())
        body.document().setTextWidth(width)
        # 增加更多空间，避免文字被切割
        body.setFixedHeight(int(body.document().size().height()) + 20)

    def show_full_image(self, image_thumbnail):
        """显示放大的原图"""
        import base64
        dialog = QDialog(self)
        dialog.setWindowTitle("查看图片")
        dialog.setModal(True)

        layout = QVBoxLayout(dialog)
        image_data = base64.b64decode(image_thumbnail)
        pixmap = QPixmap()
        pixmap.loadFromData(image_data)

        label = QLabel()
        label.setPixmap(pixmap)
        label.setScaledContents(False)
        layout.addWidget(label)

        dialog.resize(pixmap.width() + 40, pixmap.height() + 40)
        dialog.exec()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        for child in self.findChildren(QTextBrowser):
            self.adjust_body_height(child)


class ChatWindow(QWidget):
    send_requested = Signal(str)
    image_selected = Signal(str, str)  # 修改：(图片路径, 文字消息)

    STATUS_TEXT = {
        "idle": "在线",
        "thinking": "思考中",
        "typing": "回复中",
        "error": "出错了",
    }

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}

        # 从配置读取窗口尺寸
        from pet_core import get_ui_config
        min_width = get_ui_config(config, 'window', 'chat_min_width', default=560)
        min_height = get_ui_config(config, 'window', 'chat_min_height', default=520)
        default_width = get_ui_config(config, 'window', 'chat_default_width', default=720)
        default_height = get_ui_config(config, 'window', 'chat_default_height', default=720)
        pet_name = get_ui_config(config, 'text', 'pet_name', default="小爪子")
        input_placeholder = get_ui_config(config, 'text', 'input_placeholder', default="和小爪子说点什么")

        self.setWindowTitle("Chat")

        # 设置聊天窗口图标（红色爱心 emoji）
        self.setWindowIcon(self.create_emoji_icon("❤️"))

        self.setMinimumSize(min_width, min_height)
        self.resize(default_width, default_height)
        self.current_theme = THEME_LIGHT
        self.pending_image_path = None  # 待发送的图片路径
        self.messages = []  # 保存所有消息数据，用于主题切换时重建

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"{pet_name}聊天室")
        title.setObjectName("chatTitle")

        self.theme_button = ThemeToggleButton()
        self.theme_button.clicked.connect(self.toggle_theme)

        self.status_dot = StatusDot()
        self.status_label = QLabel(self.STATUS_TEXT["idle"])
        self.status_label.setObjectName("chatStatus")
        header.addWidget(title)
        header.addWidget(self.theme_button)
        header.addStretch(1)
        header.addWidget(self.status_dot)
        header.addWidget(self.status_label)
        outer.addLayout(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(10, 10, 10, 10)
        self.body_layout.setSpacing(4)
        self.body_layout.addStretch(1)
        self.scroll.setWidget(self.body)
        outer.addWidget(self.scroll, 1)

        # 图片预览区域（初始隐藏）
        self.image_preview_container = QFrame()
        self.image_preview_container.setObjectName("imagePreview")
        self.image_preview_container.setFixedHeight(80)
        preview_layout = QHBoxLayout(self.image_preview_container)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        preview_layout.setSpacing(8)

        self.image_preview_label = QLabel()
        self.image_preview_label.setFixedSize(64, 64)
        self.image_preview_label.setScaledContents(True)

        preview_info = QVBoxLayout()
        self.image_name_label = QLabel("图片名称.png")
        self.image_name_label.setObjectName("imageName")
        preview_info.addWidget(self.image_name_label)
        preview_info.addStretch(1)

        remove_button = QPushButton("×")
        remove_button.setObjectName("removeImage")
        remove_button.setCursor(Qt.PointingHandCursor)
        remove_button.setFixedSize(32, 32)
        remove_button.clicked.connect(self.clear_image_preview)

        preview_layout.addWidget(self.image_preview_label)
        preview_layout.addLayout(preview_info, 1)
        preview_layout.addWidget(remove_button)
        self.image_preview_container.hide()
        outer.addWidget(self.image_preview_container)

        composer = QHBoxLayout()
        composer.setSpacing(10)
        self.entry = ChatTextEdit()
        self.entry.setAcceptRichText(False)
        self.entry.setPlaceholderText(input_placeholder)
        self.entry.setFixedHeight(104)
        self.entry.send_requested.connect(self.emit_send)

        # 左侧按钮列：📎 按钮
        left_buttons = QVBoxLayout()
        left_buttons.setSpacing(6)

        self.attach_button = QPushButton("📎")
        self.attach_button.setObjectName("attachButton")
        self.attach_button.setCursor(Qt.PointingHandCursor)
        self.attach_button.setFixedSize(42, 42)
        self.attach_button.setToolTip("上传图片")
        self.attach_button.clicked.connect(self.select_image)
        left_buttons.addWidget(self.attach_button, 0, Qt.AlignTop)
        left_buttons.addStretch(1)

        # 右侧按钮列：Emoji 按钮 + 发送按钮
        right_buttons = QVBoxLayout()
        right_buttons.setSpacing(6)

        self.emoji_button = EmojiButton()
        self.emoji_button.clicked.connect(self.show_emoji_picker)
        self.emoji_button.picker.emoji_selected.connect(self.insert_emoji)

        self.send_button = QPushButton("发送")
        self.send_button.setObjectName("chatSend")
        self.send_button.setCursor(Qt.PointingHandCursor)
        self.send_button.setFixedSize(82, 42)
        self.send_button.clicked.connect(self.emit_send)

        right_buttons.addWidget(self.emoji_button, 0, Qt.AlignCenter)
        right_buttons.addWidget(self.send_button, 0, Qt.AlignBottom)

        composer.addLayout(left_buttons)
        composer.addWidget(self.entry, 1)
        composer.addLayout(right_buttons)
        outer.addLayout(composer)

        # 启用拖拽支持
        self.setAcceptDrops(True)

        self.apply_theme(self.current_theme)

    def create_emoji_icon(self, emoji):
        """创建 emoji 图标"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # 设置字体
        font = QFont("Segoe UI Emoji", 48)
        painter.setFont(font)

        # 绘制 emoji
        painter.drawText(pixmap.rect(), Qt.AlignCenter, emoji)
        painter.end()

        return QIcon(pixmap)

    def apply_theme(self, theme):
        """应用主题配色"""
        self.current_theme = theme
        accent = theme['accent']
        accent_hover = "#c97258" if theme == THEME_LIGHT else "#d4744e"

        self.setStyleSheet(
            f"""
            QWidget {{
                background: {theme['window_bg']};
                color: {theme['text']};
                font-family: "Microsoft YaHei UI", "Segoe UI Emoji";
            }}
            QLabel#chatTitle {{
                color: {theme['text']};
                font: 700 13pt "Microsoft YaHei UI";
            }}
            QLabel#chatStatus {{
                color: {rgba(theme['text'], 176)};
                font: 9pt "Consolas", "Microsoft YaHei UI";
            }}
            QScrollArea {{
                background: transparent;
                border: 1px solid {rgba(theme['input_border'], 150)};
                border-radius: 6px;
            }}
            QScrollBar:vertical {{
                background: transparent;
                width: 10px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {rgba(theme['input_border'], 178)};
                border-radius: 5px;
                min-height: 32px;
            }}
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            QTextEdit {{
                color: {theme['input_text']};
                background: {rgba(theme['input_bg'], 236)};
                border: 1px solid {rgba(theme['input_border'], 210)};
                border-radius: 6px;
                padding: 9px 11px;
                selection-background-color: {rgba(accent, 96)};
                font: 10pt "Microsoft YaHei UI", "Segoe UI Emoji";
            }}
            QPushButton#chatSend {{
                color: #ffffff;
                background: {accent};
                border: none;
                border-radius: 6px;
                padding: 0 18px;
                font: 700 10pt "Microsoft YaHei UI";
            }}
            QPushButton#chatSend:hover {{
                background: {accent_hover};
            }}
            QPushButton#attachButton {{
                background: {rgba(theme['input_bg'], 236)};
                border: 1px solid {rgba(theme['input_border'], 210)};
                border-radius: 6px;
                font-size: 18pt;
            }}
            QPushButton#attachButton:hover {{
                background: {rgba(theme['input_border'], 88)};
            }}
            QFrame#imagePreview {{
                background: {rgba(theme['input_bg'], 236)};
                border: 1px solid {rgba(theme['input_border'], 210)};
                border-radius: 6px;
            }}
            QLabel#imageName {{
                color: {theme['input_text']};
                font: 10pt "Microsoft YaHei UI";
            }}
            QPushButton#removeImage {{
                color: {rgba(theme['input_text'], 210)};
                background: transparent;
                border: none;
                font: 700 16pt "Microsoft YaHei UI";
            }}
            QPushButton#removeImage:hover {{
                background: {rgba(theme['input_border'], 88)};
                border-radius: 16px;
            }}
            """
        )
        self.scroll.viewport().setStyleSheet(f"background: {rgba(theme['scroll_bg'], theme['scroll_bg_alpha'])};")
        self.body.setStyleSheet("background: transparent;")

        # 重建所有消息以应用新主题
        self.rebuild_messages()

    def rebuild_messages(self):
        """重建所有消息以应用新主题颜色"""
        # 清空所有组件
        for i in reversed(range(self.body_layout.count() - 1)):
            item = self.body_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()

        # 使用保存的消息数据重建
        for role, text, timestamp, thinking, image_thumbnail in self.messages:
            item = TranscriptMessage(role, text, timestamp, theme=self.current_theme, thinking=thinking, image_thumbnail=image_thumbnail, config=self.config)
            self.body_layout.insertWidget(self.body_layout.count() - 1, item)

    def toggle_theme(self):
        """切换主题"""
        self.theme_button.toggle()
        new_theme = THEME_DARK if self.theme_button.is_dark else THEME_LIGHT
        self.apply_theme(new_theme)
        # 同步更新 Emoji 选择器主题
        self.emoji_button.picker.apply_theme(self.theme_button.is_dark)

    def add_message(self, role, text, timestamp, thinking=None, image_thumbnail=None):
        # 保存消息数据
        self.messages.append((role, text, timestamp, thinking, image_thumbnail))
        # 创建消息组件
        item = TranscriptMessage(role, text, timestamp, theme=self.current_theme, thinking=thinking, image_thumbnail=image_thumbnail, config=self.config)
        self.body_layout.insertWidget(self.body_layout.count() - 1, item)
        self.scroll_to_bottom()

    def set_status(self, state, text=None):
        self.status_dot.set_state(state)
        self.status_label.setText(text or self.STATUS_TEXT.get(state, self.STATUS_TEXT["idle"]))

    def emit_send(self):
        text = self.entry.toPlainText().strip()
        image_path = self.pending_image_path

        # 必须有文字或图片才能发送
        if not text and not image_path:
            return

        # 清空输入
        self.entry.clear()
        if image_path:
            self.clear_image_preview()

        # 如果有图片，发送图片信号（带文字）
        if image_path:
            self.image_selected.emit(image_path, text or "")
            return

        # 只有文字的情况
        self.send_requested.emit(text)

    def show_emoji_picker(self):
        """显示 Emoji 选择器"""
        button_pos = self.emoji_button.mapToGlobal(self.emoji_button.rect().bottomLeft())
        picker_x = button_pos.x() - self.emoji_button.picker.width() + self.emoji_button.width()
        picker_y = button_pos.y() + 4
        self.emoji_button.picker.move(picker_x, picker_y)
        self.emoji_button.picker.show()

    def insert_emoji(self, emoji):
        """插入 Emoji 到输入框当前光标位置"""
        cursor = self.entry.textCursor()
        cursor.insertText(emoji)
        self.entry.setFocus(Qt.OtherFocusReason)

    def select_image(self):
        """打开文件选择对话框，选择图片"""
        from PySide6.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            self.show_image_preview(file_path)

    def show_image_preview(self, file_path):
        """显示图片预览"""
        import os
        from PySide6.QtCore import QUrl

        # 如果是 file:// URL，转换为本地路径
        if file_path.startswith('file://'):
            file_path = QUrl(file_path).toLocalFile()

        self.pending_image_path = file_path

        # 加载缩略图
        pixmap = QPixmap(file_path)
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.image_preview_label.setPixmap(scaled_pixmap)
            self.image_name_label.setText(os.path.basename(file_path))
            self.image_preview_container.show()
        else:
            # 如果加载失败，显示错误
            self.image_name_label.setText(f"加载失败: {os.path.basename(file_path)}")
            self.image_preview_container.show()

    def clear_image_preview(self):
        """清除图片预览"""
        self.pending_image_path = None
        self.image_preview_label.clear()
        self.image_name_label.clear()
        self.image_preview_container.hide()

    def dragEnterEvent(self, event):
        """拖拽进入窗口时触发"""
        if event.mimeData().hasUrls():
            # 检查是否有图片文件
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragMoveEvent(self, event):
        """拖拽在窗口内移动时触发"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        """拖拽释放时触发 - 显示预览而不是立即发送"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                    self.show_image_preview(file_path)
                    event.acceptProposedAction()
                    return
        event.ignore()

    def focus_input(self):
        self.entry.setFocus(Qt.OtherFocusReason)

    def scroll_to_bottom(self):
        """滚动到底部，多次尝试确保成功"""
        def do_scroll():
            self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            )

        # 立即滚动一次
        QTimer.singleShot(0, do_scroll)
        # 再延迟滚动一次（确保内容渲染完成）
        QTimer.singleShot(100, do_scroll)
        # 最后再滚动一次（确保思维链等组件高度计算完成）
        QTimer.singleShot(300, do_scroll)

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class InputBar(QFrame):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config or {}
        self.setObjectName("inputBar")

        # 从配置读取输入框高度和占位文本
        from pet_core import get_ui_config
        input_bar_height = get_ui_config(config, 'pet', 'input_bar_height', default=52)
        input_placeholder = get_ui_config(config, 'text', 'input_placeholder', default="和小爪子说点什么")

        self.setFixedHeight(input_bar_height)
        self.setStyleSheet(
            f"""
            QFrame#inputBar {{
                background: {rgba(INPUT_PANEL_BG, 132)};
                border: 1px solid {rgba(INPUT_BORDER, 156)};
                border-radius: 24px;
            }}
            QLineEdit {{
                color: {INPUT_TEXT};
                background: {rgba(INPUT_BG, 162)};
                border: 1px solid {rgba(INPUT_BORDER, 168)};
                border-radius: 17px;
                padding: 0 13px;
                selection-background-color: {rgba(ACCENT, 96)};
                font: 10pt "Microsoft YaHei UI";
            }}
            """
        )
        add_shadow(self, blur=24, y=8, alpha=48)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.history_button = IconGlassButton("history")
        self.history_button.setToolTip("聊天记录")
        self.chat_button = IconGlassButton("chat")
        self.chat_button.setToolTip("正式聊天")
        self.status_dot = StatusDot()
        self.eye_indicator = EyeIndicator()
        self.eye_indicator.setToolTip("截图状态")
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(input_placeholder)
        self.entry.setFixedHeight(34)
        self.send_button = IconGlassButton("send")
        self.send_button.setToolTip("发送")
        self.close_button = QPushButton("×")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.setFixedSize(30, 34)
        self.close_button.setStyleSheet(
            f"""
            QPushButton {{
                color: {rgba(INPUT_TEXT, 190)};
                background: transparent;
                border: none;
                font: 700 12pt "Microsoft YaHei UI";
            }}
            QPushButton:hover {{
                background: {rgba(INPUT_BORDER, 84)};
                border-radius: 15px;
            }}
            """
        )

        layout.addWidget(self.history_button)
        layout.addWidget(self.status_dot)
        layout.addWidget(self.eye_indicator)
        layout.addWidget(self.entry, 1)
        layout.addWidget(self.chat_button)
        layout.addWidget(self.send_button)
        layout.addWidget(self.close_button)
