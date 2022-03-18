"""Support for the for Danfoss Air HRV binary sensors."""
from __future__ import annotations

from pydanfossair.commands import ReadCommand

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import DOMAIN as DANFOSS_AIR_DOMAIN


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the available Danfoss Air sensors etc."""
    data = hass.data[DANFOSS_AIR_DOMAIN]

    sensors = [
        [
            "Danfoss Air Bypass Active",
            ReadCommand.bypass,
            BinarySensorDeviceClass.OPENING,
        ],
        ["Danfoss Air Away Mode Active", ReadCommand.away_mode, None],
    ]

    dev = []

    for sensor in sensors:
        dev.append(DanfossAirBinarySensor(data, sensor[0], sensor[1], sensor[2]))

    add_entities(dev, True)


class DanfossAirBinarySensor(BinarySensorEntity):
    """Representation of a Danfoss Air binary sensor."""

    def __init__(self, data, name, sensor_type, device_class):
        """Initialize the Danfoss Air binary sensor."""
        self._data = data
        self._attr_name = name
        self._type = sensor_type
        self._attr_device_class = device_class

    def update(self):
        """Fetch new state data for the sensor."""
        self._data.update()

        self._attr_is_on = self._data.get_value(self._type)
