"""Support for Eight Sleep binary sensors."""
from __future__ import annotations

import logging

from pyeight.eight import EightSleep

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import EightSleepBaseEntity
from .const import DATA_API, DATA_HEAT, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the eight sleep binary sensor."""
    if discovery_info is None:
        return

    eight: EightSleep = hass.data[DOMAIN][DATA_API]
    heat_coordinator: DataUpdateCoordinator = hass.data[DOMAIN][DATA_HEAT]

    entities = []
    for user in eight.users.values():
        entities.append(
            EightHeatSensor(heat_coordinator, eight, user.userid, "bed_presence")
        )

    async_add_entities(entities)


class EightHeatSensor(EightSleepBaseEntity, BinarySensorEntity):
    """Representation of a Eight Sleep heat-based sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        eight: EightSleep,
        user_id: str | None,
        sensor: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, eight, user_id, sensor)
        assert self._user_obj
        _LOGGER.debug(
            "Presence Sensor: %s, Side: %s, User: %s",
            sensor,
            self._user_obj.side,
            user_id,
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        assert self._user_obj
        return bool(self._user_obj.bed_presence)
