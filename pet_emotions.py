"""Shared pet emotion registry.

Keep the emotion names here in sync with the visual assets and Claude prompt.
Qt uses the GIF/SVG maps for playback; pet_core uses the public names and usage
tips to validate hidden pet-emotion blocks.
"""

EMOTION_GROUPS = {
    "state": [
        "idle",
        "thinking",
        "typing",
        "error",
        "notification",
    ],
    "expression": [
        "happy",
        "question",
        "double_jump",
        "swag",
    ],
    "work": [
        "debugger",
        "conducting",
        "juggling",
        "sweeping",
        "building",
        "carrying",
    ],
    "idle_action": [
        "idle_doze",
        "idle_yawn",
        "idle_reading",
        "sleeping",
    ],
}

GIF_EMOTIONS = {
    "idle": "clawd-idle.gif",
    "idle_reading": "clawd-idle-reading.gif",
    "thinking": "clawd-thinking.gif",
    "typing": "clawd-typing.gif",
    "happy": "clawd-happy.gif",
    "error": "clawd-error.gif",
    "notification": "clawd-notification.gif",
    "sleeping": "clawd-sleeping.gif",
    "debugger": "clawd-debugger.gif",
    "building": "clawd-building.gif",
    "carrying": "clawd-carrying.gif",
    "conducting": "clawd-conducting.gif",
    "juggling": "clawd-juggling.gif",
    "sweeping": "clawd-sweeping.gif",
    "question": "clawd-react-annoyed.gif",
    "double_jump": "clawd-react-double-jump.gif",
}

SVG_EMOTIONS = {
    "idle": "clawd-idle-living.svg",
    "idle_look": "clawd-idle-look.svg",
    "idle_doze": "clawd-idle-doze.svg",
    "idle_yawn": "clawd-idle-yawn.svg",
    "idle_reading": "clawd-idle-reading.svg",
    "thinking": "clawd-working-thinking.svg",
    "typing": "clawd-working-typing.svg",
    "happy": "clawd-happy.svg",
    "error": "clawd-error.svg",
    "notification": "clawd-notification.svg",
    "sleeping": "clawd-sleeping.svg",
    "debugger": "clawd-working-debugger.svg",
    "building": "clawd-working-building.svg",
    "carrying": "clawd-working-carrying.svg",
    "conducting": "clawd-working-conducting.svg",
    "juggling": "clawd-working-juggling.svg",
    "sweeping": "clawd-working-sweeping.svg",
    "question": "clawd-react-annoyed.svg",
    "double_jump": "clawd-react-double-jump.svg",
    "swag": "clawd-about-hero.svg",
}

SVG_SCALE = {
    "swag": 0.42,
}

IDLE_ACTIONS = [
    "idle_doze",
    "idle_yawn",
    "idle_reading",
    "sleeping",
]

CLAUDE_EMOTIONS = [
    "happy",
    "question",
    "double_jump",
    "debugger",
    "conducting",
    "juggling",
    "sweeping",
    "building",
    "carrying",
    "notification",
    "sleeping",
    "swag",
    "idle",
]

def emotion_names_for_prompt():
    return ", ".join(CLAUDE_EMOTIONS)
