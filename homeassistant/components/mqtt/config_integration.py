"""Support for MQTT platform config setup."""

import probatio

from homeassistant.const import Platform

CONFIG_SCHEMA_BASE = probatio.Schema(
    {
        Platform.ALARM_CONTROL_PANEL.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.BINARY_SENSOR.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.BUTTON.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.CAMERA.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.CLIMATE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.COVER.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.DATE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.DATETIME.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.DEVICE_TRACKER.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.EVENT.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.FAN.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.HUMIDIFIER.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.IMAGE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.INFRARED.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.LAWN_MOWER.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.LIGHT.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.LOCK.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.NOTIFY.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.NUMBER.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.SCENE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.SELECT.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.SENSOR.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.SIREN.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.SWITCH.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.TEXT.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.TIME.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.UPDATE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.VACUUM.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.VALVE.value: probatio.All(probatio.EnsureList(), [dict]),
        Platform.WATER_HEATER.value: probatio.All(probatio.EnsureList(), [dict]),
    }
)
