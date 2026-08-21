"""Support for MQTT platform config setup."""

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA_BASE = vol.Schema(
    {
        Platform.ALARM_CONTROL_PANEL.value: vol.All(cv.ensure_list, [dict]),
        Platform.BINARY_SENSOR.value: vol.All(cv.ensure_list, [dict]),
        Platform.BUTTON.value: vol.All(cv.ensure_list, [dict]),
        Platform.CAMERA.value: vol.All(cv.ensure_list, [dict]),
        Platform.CLIMATE.value: vol.All(cv.ensure_list, [dict]),
        Platform.COVER.value: vol.All(cv.ensure_list, [dict]),
        Platform.DATE.value: vol.All(cv.ensure_list, [dict]),
        Platform.DATETIME.value: vol.All(cv.ensure_list, [dict]),
        Platform.DEVICE_TRACKER.value: vol.All(cv.ensure_list, [dict]),
        Platform.EVENT.value: vol.All(cv.ensure_list, [dict]),
        Platform.FAN.value: vol.All(cv.ensure_list, [dict]),
        Platform.HUMIDIFIER.value: vol.All(cv.ensure_list, [dict]),
        Platform.IMAGE.value: vol.All(cv.ensure_list, [dict]),
        Platform.INFRARED.value: vol.All(cv.ensure_list, [dict]),
        Platform.LAWN_MOWER.value: vol.All(cv.ensure_list, [dict]),
        Platform.LIGHT.value: vol.All(cv.ensure_list, [dict]),
        Platform.LOCK.value: vol.All(cv.ensure_list, [dict]),
        Platform.NOTIFY.value: vol.All(cv.ensure_list, [dict]),
        Platform.NUMBER.value: vol.All(cv.ensure_list, [dict]),
        Platform.SCENE.value: vol.All(cv.ensure_list, [dict]),
        Platform.SELECT.value: vol.All(cv.ensure_list, [dict]),
        Platform.SENSOR.value: vol.All(cv.ensure_list, [dict]),
        Platform.SIREN.value: vol.All(cv.ensure_list, [dict]),
        Platform.SWITCH.value: vol.All(cv.ensure_list, [dict]),
        Platform.TEXT.value: vol.All(cv.ensure_list, [dict]),
        Platform.TIME.value: vol.All(cv.ensure_list, [dict]),
        Platform.UPDATE.value: vol.All(cv.ensure_list, [dict]),
        Platform.VACUUM.value: vol.All(cv.ensure_list, [dict]),
        Platform.VALVE.value: vol.All(cv.ensure_list, [dict]),
        Platform.WATER_HEATER.value: vol.All(cv.ensure_list, [dict]),
    }
)
