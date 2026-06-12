#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PySide6 visual prototype for the desktop pet."""

import sys
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QMovie
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from pet_ui import PET_SIZE
from qt_pet_ui import HistoryDrawer, InputBar


class QtPetPrototype(QWidget):
    def __init__(self):
        super().__init__()
        self.app_dir = Path(__file__).resolve().parent
        self.drag_offset = QPoint()

        self.setWindowTitle("Clawd Qt Prototype")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(420, 230)

        self.pet_label = QLabel(self)
        self.pet_label.setFixedSize(PET_SIZE, PET_SIZE)
        self.pet_label.setScaledContents(True)
        self.pet_label.move((self.width() - PET_SIZE) // 2, 0)
        self.load_pet_movie()

        self.input_bar = InputBar(self)
        self.input_bar.setFixedWidth(330)
        self.input_bar.move((self.width() - self.input_bar.width()) // 2, PET_SIZE + 10)

        self.history = HistoryDrawer(self)
        self.history.move((self.width() - self.history.width()) // 2, PET_SIZE + 70)
        self.history.hide()

        self.input_bar.close_button.clicked.connect(self.input_bar.hide)
        self.input_bar.history_button.clicked.connect(self.toggle_history)
        self.input_bar.send_button.clicked.connect(self.send_mock_message)
        self.input_bar.entry.returnPressed.connect(self.send_mock_message)
        self.pet_label.mousePressEvent = self.pet_mouse_press

        self.history.add_message("assistant", "PySide6 原型启动。这里用于验证输入条、状态点和聊天抽屉。")
        self.move_to_bottom_right()

    def load_pet_movie(self):
        gif_path = self.app_dir / "gif" / "clawd-idle.gif"
        if gif_path.exists():
            self.movie = QMovie(str(gif_path))
            self.movie.setScaledSize(self.pet_label.size())
            self.pet_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.pet_label.setText("Clawd")
            self.pet_label.setAlignment(Qt.AlignCenter)

    def move_to_bottom_right(self):
        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.right() - self.width() - 20
        y = screen.bottom() - self.height() - 20
        self.move(x, y)

    def toggle_history(self):
        self.history.setVisible(not self.history.isVisible())

    def send_mock_message(self):
        text = self.input_bar.entry.text().strip()
        if not text:
            return
        self.input_bar.entry.clear()
        self.input_bar.status_dot.set_state("thinking")
        self.history.add_message("user", text)
        self.history.show()
        QTimer.singleShot(450, lambda: self.mock_reply(text))

    def mock_reply(self, text):
        self.input_bar.status_dot.set_state("typing")
        self.history.add_message("assistant", f"收到：{text}")
        QTimer.singleShot(600, lambda: self.input_bar.status_dot.set_state("idle"))

    def pet_mouse_press(self, event):
        if event.button() == Qt.LeftButton:
            self.input_bar.setVisible(not self.input_bar.isVisible())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = QtPetPrototype()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
