"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

import asyncio
import logging
from typing import Union

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .const import (
    DEVICE_INFO,
    DOMAIN,
    SENSOR_TYPE_RAINDELAY,
    SENSOR_TYPE_RAINSENSOR,
    SERIAL_NUMBER,
)
from .coordinator import RainbirdUpdateCoordinator


_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key=SENSOR_TYPE_RAINSENSOR,
        name="Rainsensor",
        icon="mdi:water",
    ),
    BinarySensorEntityDescription(
        key=SENSOR_TYPE_RAINDELAY,
        name="Raindelay",
        icon="mdi:water-off",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird binary_sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    await asyncio.gather(
        *[
            data[description.key].async_config_entry_first_refresh()
            for description in SENSOR_TYPES
        ],
    )
    async_add_devices(
        RainBirdSensor(
            data[description.key], description, data[SERIAL_NUMBER], data[DEVICE_INFO]
        )
        for description in SENSOR_TYPES
    )


class RainBirdSensor(
    CoordinatorEntity[RainbirdUpdateCoordinator[Union[int, bool]]], BinarySensorEntity
):
    """A sensor implementation for Rain Bird device."""

    def __init__(
        self,
        coordinator: RainbirdUpdateCoordinator[int | bool],
        description: BinarySensorEntityDescription,
        serial_number: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the Rain Bird sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{serial_number}-{description.key}"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool | None:
        """Return True if entity is on."""
        return None if self.coordinator.data is None else bool(self.coordinator.data)
