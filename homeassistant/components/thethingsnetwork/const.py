"""The Things Network's integration constants."""

from homeassistant.const import Platform

DOMAIN = "thethingsnetwork"
TTN_API_HOSTNAME = "eu1.cloud.thethings.network"

PLATFORMS = [Platform.SENSOR]

CONF_HOSTNAME = "hostname"
CONF_API_KEY = "access_key"
CONF_APP_ID = "app_id"

POLLING_PERIOD_S = 60
FIRST_FETCH_H = 24
