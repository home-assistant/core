"""Constants for the QuickBars integration."""

ALLOWED_DOMAINS = [
    "light",
    "switch",
    "button",
    "fan",
    "input_boolean",
    "input_button",
    "script",
    "scene",
    "climate",
    "cover",
    "sensor",
    "binary_sensor",
    "lock",
    "alarm_control_panel",
    "camera",
    "automation",
    "media_player",
]
DOMAIN = "quickbars"

EVENT_NAME = "quickbars.open"
SERVICE_TYPE = "_quickbars._tcp.local."

# camera positions
POS_CHOICES = ["top_left", "top_right", "bottom_left", "bottom_right"]
