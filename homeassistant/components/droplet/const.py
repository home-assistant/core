"""Constants for the droplet integration."""

import enum

# Keys for values used in the config_entry data dictionary
CONF_HOST = "droplet_host"
CONF_PORT = "droplet_port"
CONF_DEVICE_ID = "device_id"
CONF_DEVICE_NAME = "name"
CONF_MANUFACTURER = "manufacturer"
CONF_MODEL = "model"
CONF_SW = "sw"
CONF_SERIAL = "sn"
CONF_PAIRING_CODE = "pairing_code"

RECONNECT_DELAY = 5

DOMAIN = "droplet"
DEVICE_NAME = "Droplet"

KEY_CURRENT_FLOW_RATE = "current_flow_rate"
KEY_VOLUME = "volume"
KEY_SIGNAL_QUALITY = "signal_quality"
KEY_SERVER_CONNECTIVITY = "server_connectivity"


class AccumulatedVolume(enum.StrEnum):
    """Represent a time interval."""

    DAILY = "daily_volume"
    WEEKLY = "weekly_volume"
    MONTHLY = "monthly_volume"
