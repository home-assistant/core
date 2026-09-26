"""Support for MQTT platform config setup."""

import probatio

from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA_BASE = probatio.Schema(
    {
        Platform.ALARM_CONTROL_PANEL.value: probatio.All(cv.ensure_list, [dict]),
        Platform.BINARY_SENSOR.value: probatio.All(cv.ensure_list, [dict]),
        Platform.BUTTON.value: probatio.All(cv.ensure_list, [dict]),
        Platform.CAMERA.value: probatio.All(cv.ensure_list, [dict]),
        Platform.CLIMATE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.COVER.value: probatio.All(cv.ensure_list, [dict]),
        Platform.DATE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.DATETIME.value: probatio.All(cv.ensure_list, [dict]),
        Platform.DEVICE_TRACKER.value: probatio.All(cv.ensure_list, [dict]),
        Platform.EVENT.value: probatio.All(cv.ensure_list, [dict]),
        Platform.FAN.value: probatio.All(cv.ensure_list, [dict]),
        Platform.HUMIDIFIER.value: probatio.All(cv.ensure_list, [dict]),
        Platform.IMAGE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.INFRARED.value: probatio.All(cv.ensure_list, [dict]),
        Platform.LAWN_MOWER.value: probatio.All(cv.ensure_list, [dict]),
        Platform.LIGHT.value: probatio.All(cv.ensure_list, [dict]),
        Platform.LOCK.value: probatio.All(cv.ensure_list, [dict]),
        Platform.NOTIFY.value: probatio.All(cv.ensure_list, [dict]),
        Platform.NUMBER.value: probatio.All(cv.ensure_list, [dict]),
        Platform.SCENE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.SELECT.value: probatio.All(cv.ensure_list, [dict]),
        Platform.SENSOR.value: probatio.All(cv.ensure_list, [dict]),
        Platform.SIREN.value: probatio.All(cv.ensure_list, [dict]),
        Platform.SWITCH.value: probatio.All(cv.ensure_list, [dict]),
        Platform.TEXT.value: probatio.All(cv.ensure_list, [dict]),
        Platform.TIME.value: probatio.All(cv.ensure_list, [dict]),
        Platform.UPDATE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.VACUUM.value: probatio.All(cv.ensure_list, [dict]),
        Platform.VALVE.value: probatio.All(cv.ensure_list, [dict]),
        Platform.WATER_HEATER.value: probatio.All(cv.ensure_list, [dict]),
    }
)
