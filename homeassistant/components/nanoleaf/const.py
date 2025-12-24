"""Constants for Nanoleaf integration."""

DOMAIN = "nanoleaf"

NANOLEAF_EVENT = f"{DOMAIN}_event"

TOUCH_MODELS = {"NL29", "NL42", "NL52"}

EMERSION_MODELS = {"NL69"}

EMERSION_MODES = ["1D", "2D", "3D", "4D"]

TOUCH_GESTURE_TRIGGER_MAP = {
    2: "swipe_up",
    3: "swipe_down",
    4: "swipe_left",
    5: "swipe_right",
}
