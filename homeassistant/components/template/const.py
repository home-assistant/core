"""Constants for the Template Platform Components."""

CONF_AVAILABILITY_TEMPLATE = "availability_template"
CONF_ATTRIBUTE_TEMPLATES = "attribute_templates"
CONF_TRIGGER = "trigger"

DOMAIN = "template"

PLATFORM_STORAGE_KEY = "template_platforms"

PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "cover",
    "fan",
    "light",
    "lock",
    "sensor",
    "switch",
    "vacuum",
    "weather",
]
