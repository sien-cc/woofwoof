"""Shared colors and dimensions for the PySide6 desktop pet."""

CHAT_PANEL = "#fffdf8"
CHAT_TEXT = "#3b2418"
USER_BUBBLE = "#ffd7a8"
ASSISTANT_BUBBLE = "#f4eadf"
ACCENT = "#de886d"

INPUT_PANEL_BG = CHAT_PANEL
INPUT_BG = "#fffaf4"
INPUT_BORDER = "#efc5a3"
INPUT_TEXT = CHAT_TEXT

BUBBLE_TEXT = CHAT_TEXT
USER_BUBBLE_OUTLINE = "#e5a879"
ASSISTANT_BUBBLE_OUTLINE = "#dbc4b2"

# Theme system
THEME_LIGHT = {
    'name': 'light',
    'window_bg': CHAT_PANEL,
    'scroll_bg': INPUT_BG,
    'scroll_bg_alpha': 92,
    'text': CHAT_TEXT,
    'timestamp': CHAT_TEXT,
    'timestamp_alpha': 120,
    'user_role': USER_BUBBLE_OUTLINE,
    'assistant_role': ACCENT,
    'input_bg': INPUT_BG,
    'input_border': INPUT_BORDER,
    'input_text': CHAT_TEXT,
    'accent': ACCENT,
}

THEME_DARK = {
    'name': 'dark',
    'window_bg': '#1e1e1e',
    'scroll_bg': '#252526',
    'scroll_bg_alpha': 255,
    'text': '#d4d4d4',
    'timestamp': '#808080',
    'timestamp_alpha': 255,
    'user_role': '#64b5f6',
    'assistant_role': '#ff8a65',
    'input_bg': '#2d2d2d',
    'input_border': '#3e3e3e',
    'input_text': '#cccccc',
    'accent': '#ff8a65',
}

PET_SIZE = 120

WINDOW_MARGIN = 8
PET_WINDOW_GAP = 8
BUBBLE_GAP = 6

USER_BUBBLE_MIN_WIDTH = 240
USER_BUBBLE_MIN_HEIGHT = 58
ASSISTANT_BUBBLE_MIN_WIDTH = 260
ASSISTANT_BUBBLE_MIN_HEIGHT = 70

HISTORY_BUBBLE_MAX_WIDTH = 320
HISTORY_WINDOW_PET_GAP = 10
