"""The Things Network's integration constants."""

from homeassistant.const import Platform

DOMAIN = "thethingsnetwork"
TTN_API_HOST = "eu1.cloud.thethings.network"

PLATFORMS = [Platform.SENSOR]

CONF_APP_ID = "app_id"
CONF_FIRST_FETCH_H = "first_fetch_h"

DEFAULT_FIRST_FETCH_H = 24
FIRST_FETCH_OPTIONS = ["1", "3", "6", "12", "24"]

POLLING_PERIOD_S = 60
