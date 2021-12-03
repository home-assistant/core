"""Support for Eight Sleep binary sensors."""
from __future__ import annotations

import logging

from pyeight.eight import EightSleep

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_OCCUPANCY,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import (
    CONF_BINARY_SENSORS,
    DATA_API,
    DATA_EIGHT,
    DATA_HEAT,
    EightSleepBaseEntity,
    EightSleepHeatDataCoordinator,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType = None,
) -> None:
    """Set up the eight sleep binary sensor."""
    if discovery_info is None:
        return

    name = "Eight"
    sensors = discovery_info[CONF_BINARY_SENSORS]
    eight: EightSleep = hass.data[DATA_EIGHT][DATA_API]
    heat_coordinator: EightSleepHeatDataCoordinator = hass.data[DATA_EIGHT][DATA_HEAT]

    all_sensors = [
        EightHeatSensor(name, heat_coordinator, eight, side, sensor)
        for side, sensor in sensors
    ]

    async_add_entities(all_sensors)


class EightHeatSensor(EightSleepBaseEntity, BinarySensorEntity):
    """Representation of a Eight Sleep heat-based sensor."""

    def __init__(
        self,
        name: str,
        coordinator: EightSleepHeatDataCoordinator,
        eight: EightSleep,
        side: str | None,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(name, coordinator, eight, side, sensor)
        self._attr_device_class = DEVICE_CLASS_OCCUPANCY

        _LOGGER.debug(
            "Presence Sensor: %s, Side: %s, User: %s",
            self._sensor,
            self._side,
            self._usrobj.userid,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return bool(self._usrobj.bed_presence)
