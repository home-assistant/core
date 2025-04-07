"""Constants for LG ThinQ."""

from datetime import timedelta
from typing import Final

from homeassistant.const import UnitOfTemperature

# Config flow
DOMAIN = "lg_thinq"
COMPANY = "LGE"
DEFAULT_COUNTRY: Final = "US"
THINQ_DEFAULT_NAME: Final = "LG ThinQ"
THINQ_PAT_URL: Final = "https://connect-pat.lgthinq.com"
CLIENT_PREFIX: Final = "home-assistant"
CONF_CONNECT_CLIENT_ID: Final = "connect_client_id"

# MQTT
MQTT_SUBSCRIPTION_INTERVAL: Final = timedelta(days=1)

# MQTT: Message types
DEVICE_PUSH_MESSAGE: Final = "DEVICE_PUSH"
DEVICE_STATUS_MESSAGE: Final = "DEVICE_STATUS"

# Unit conversion map
DEVICE_UNIT_TO_HA: dict[str, str] = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}
REVERSE_DEVICE_UNIT_TO_HA = {v: k for k, v in DEVICE_UNIT_TO_HA.items()}
