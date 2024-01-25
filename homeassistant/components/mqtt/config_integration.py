"""Support for MQTT platform config setup."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_DISCOVERY,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
    CONF_DISCOVERY_PREFIX,
    CONF_KEEPALIVE,
    CONF_TLS_INSECURE,
    CONF_WILL_MESSAGE,
)

DEFAULT_TLS_PROTOCOL = "auto"

CONFIG_SCHEMA_BASE = vol.Schema(
    {
        Platform.ALARM_CONTROL_PANEL.value: vol.All(cv.ensure_list, [dict]),
        Platform.BINARY_SENSOR.value: vol.All(cv.ensure_list, [dict]),
        Platform.BUTTON.value: vol.All(cv.ensure_list, [dict]),
        Platform.CAMERA.value: vol.All(cv.ensure_list, [dict]),
        Platform.CLIMATE.value: vol.All(cv.ensure_list, [dict]),
        Platform.COVER.value: vol.All(cv.ensure_list, [dict]),
        Platform.DEVICE_TRACKER.value: vol.All(cv.ensure_list, [dict]),
        Platform.EVENT.value: vol.All(cv.ensure_list, [dict]),
        Platform.FAN.value: vol.All(cv.ensure_list, [dict]),
        Platform.HUMIDIFIER.value: vol.All(cv.ensure_list, [dict]),
        Platform.IMAGE.value: vol.All(cv.ensure_list, [dict]),
        Platform.LAWN_MOWER.value: vol.All(cv.ensure_list, [dict]),
        Platform.LIGHT.value: vol.All(cv.ensure_list, [dict]),
        Platform.LOCK.value: vol.All(cv.ensure_list, [dict]),
        Platform.NUMBER.value: vol.All(cv.ensure_list, [dict]),
        Platform.SCENE.value: vol.All(cv.ensure_list, [dict]),
        Platform.SELECT.value: vol.All(cv.ensure_list, [dict]),
        Platform.SENSOR.value: vol.All(cv.ensure_list, [dict]),
        Platform.SIREN.value: vol.All(cv.ensure_list, [dict]),
        Platform.SWITCH.value: vol.All(cv.ensure_list, [dict]),
        Platform.TEXT.value: vol.All(cv.ensure_list, [dict]),
        Platform.UPDATE.value: vol.All(cv.ensure_list, [dict]),
        Platform.VACUUM.value: vol.All(cv.ensure_list, [dict]),
        Platform.VALVE.value: vol.All(cv.ensure_list, [dict]),
        Platform.WATER_HEATER.value: vol.All(cv.ensure_list, [dict]),
    }
)


CLIENT_KEY_AUTH_MSG = (
    "client_key and client_cert must both be present in the MQTT broker configuration"
)

DEPRECATED_CONFIG_KEYS = [
    CONF_BIRTH_MESSAGE,
    CONF_BROKER,
    CONF_CLIENT_ID,
    CONF_DISCOVERY,
    CONF_DISCOVERY_PREFIX,
    CONF_KEEPALIVE,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TLS_INSECURE,
    CONF_USERNAME,
    CONF_WILL_MESSAGE,
]

DEPRECATED_CERTIFICATE_CONFIG_KEYS = [
    CONF_CERTIFICATE,
    CONF_CLIENT_CERT,
    CONF_CLIENT_KEY,
]
