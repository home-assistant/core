"""Constants for the Smappee integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "smappee"
DATA_CLIENT = "smappee_data"

CONF_HOSTNAME = "hostname"
CONF_SERIALNUMBER = "serialnumber"
CONF_TITLE = "title"

ENV_CLOUD = "cloud"
ENV_LOCAL = "local"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH]

SUPPORTED_LOCAL_DEVICES = ("Smappee1", "Smappee2", "Smappee50")

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=20)

AUTHORIZE_URL = {
    "PRODUCTION": "https://app1pub.smappee.net/dev/v1/oauth2/authorize",
    "ACCEPTANCE": "https://farm2pub.smappee.net/dev/v1/oauth2/authorize",
    "DEVELOPMENT": "https://farm3pub.smappee.net/dev/v1/oauth2/authorize",
}
TOKEN_URL = {
    "PRODUCTION": "https://app1pub.smappee.net/dev/v3/oauth2/token",
    "ACCEPTANCE": "https://farm2pub.smappee.net/dev/v3/oauth2/token",
    "DEVELOPMENT": "https://farm3pub.smappee.net/dev/v3/oauth2/token",
}
