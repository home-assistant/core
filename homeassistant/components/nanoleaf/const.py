"""Constants for Nanoleaf integration."""

DOMAIN = "nanoleaf"

NANOLEAF_EVENT = f"{DOMAIN}_event"

TOUCH_MODELS = {"NL29", "NL42", "NL52"}

# Nanoleaf Essentials models use a different API without effects support
ESSENTIALS_MODEL_PREFIXES = ("NL71", "NL72", "NL73", "NL75")

TOUCH_GESTURE_TRIGGER_MAP = {
    2: "swipe_up",
    3: "swipe_down",
    4: "swipe_left",
    5: "swipe_right",
}
