"""Constants for the Switcher integration."""

DOMAIN = "switcher_kis"

API_CONTROL_BREEZE_DEVICE = "control_breeze_device"

DISCOVERY_TIME_SEC = 12

SIGNAL_DEVICE_ADD = "switcher_device_add"

# Configuration
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_KEY = "device_key"
CONF_DEVICE_TYPE = "device_type"

# Services
CONF_AUTO_OFF = "auto_off"
CONF_TIMER_MINUTES = "timer_minutes"
SERVICE_SET_AUTO_OFF_NAME = "set_auto_off"
SERVICE_TURN_ON_WITH_TIMER_NAME = "turn_on_with_timer"

# Defines the maximum interval device must send an update before it marked unavailable
MAX_UPDATE_INTERVAL_SEC = 30

# Defines polling interval for manually configured devices (no UDP broadcasts)
MANUAL_DEVICE_POLLING_INTERVAL_SEC = 60

PREREQUISITES_URL = (
    "https://www.home-assistant.io/integrations/switcher_kis/#prerequisites"
)
