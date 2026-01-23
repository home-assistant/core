"""Constants for the Victron VRM Solar Forecast integration."""

import logging

DOMAIN = "victron_remote_monitoring"
LOGGER = logging.getLogger(__package__)

CONF_SITE_ID = "site_id"
CONF_API_TOKEN = "api_token"

CONF_MQTT_UPDATE_FREQUENCY_SECONDS = "mqtt_update_frequency"

DEFAULT_MQTT_UPDATE_FREQUENCY_SECONDS = 5

SWITCH_ON = "On"
SWITCH_OFF = "Off"
