"""The Things Network's integration constants."""

from homeassistant.const import Platform

DOMAIN = "thethingsnetwork"
TTN_API_HOST = "eu1.cloud.thethings.network"

PLATFORMS = [Platform.SENSOR]

CONF_APP_ID = "app_id"

POLLING_PERIOD_S = 60
