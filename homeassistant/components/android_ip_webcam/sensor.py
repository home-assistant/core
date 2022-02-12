"""Support for Android IP Webcam sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_HOST,
    CONF_NAME,
    CONF_SENSORS,
    DATA_IP_WEBCAM,
    ICON_MAP,
    KEY_MAP,
    AndroidIPCamEntity,
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the IP Webcam Sensor."""
    if discovery_info is None:
        return

    host = discovery_info[CONF_HOST]
    name = discovery_info[CONF_NAME]
    sensors = discovery_info[CONF_SENSORS]
    ipcam = hass.data[DATA_IP_WEBCAM][host]

    all_sensors = []

    for sensor in sensors:
        all_sensors.append(IPWebcamSensor(name, host, ipcam, sensor))

    async_add_entities(all_sensors, True)


class IPWebcamSensor(AndroidIPCamEntity, SensorEntity):
    """Representation of a IP Webcam sensor."""

    def __init__(self, name, host, ipcam, sensor):
        """Initialize the sensor."""
        super().__init__(host, ipcam)

        self._sensor = sensor
        self._mapped_name = KEY_MAP.get(self._sensor, self._sensor)
        self._attr_name = f"{name} {self._mapped_name}"
        self._attr_native_value = None
        self._attr_native_unit_of_measurement = None

    async def async_update(self):
        """Retrieve latest state."""
        if self._sensor in ("audio_connections", "video_connections"):
            if not self._ipcam.status_data:
                return
            self._attr_native_value = self._ipcam.status_data.get(self._sensor)
            self._attr_native_unit_of_measurement = "Connections"
        else:
            (
                self._attr_native_value,
                self._attr_native_unit_of_measurement,
            ) = self._ipcam.export_sensor(self._sensor)

    @property
    def icon(self):
        """Return the icon for the sensor."""
        if self._sensor == "battery_level" and self._attr_native_value is not None:
            return icon_for_battery_level(int(self._attr_native_value))
        return ICON_MAP.get(self._sensor, "mdi:eye")
