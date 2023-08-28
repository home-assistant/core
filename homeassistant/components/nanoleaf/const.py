"""Constants for Nanoleaf integration."""

DOMAIN = "nanoleaf"

NANOLEAF_EVENT = f"{DOMAIN}_event"

TOUCH_MODELS = {"NL29", "NL42", "NL52"}

TOUCH_GESTURE_TRIGGER_MAP = {
    0: "single_tap",
    1: "double_tap",
    2: "swipe_up",
    3: "swipe_down",
    4: "swipe_left",
    5: "swipe_right",
}

NANOLEAF_PANEL_ID = "panel_id"
