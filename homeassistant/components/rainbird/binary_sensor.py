"""Support for Rain Bird Irrigation system LNK WiFi Module."""
from __future__ import annotations

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
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPE_RAINSENSOR
from .coordinator import RainbirdUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


RAIN_SENSOR_ENTITY_DESCRIPTION = BinarySensorEntityDescription(
    key=SENSOR_TYPE_RAINSENSOR,
    name="Rainsensor",
    icon="mdi:water",
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Rain Bird binary_sensor."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = RainbirdUpdateCoordinator(
        hass, "Rain", data.controller.get_rain_sensor_state
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [
            RainBirdSensor(
                coordinator,
                RAIN_SENSOR_ENTITY_DESCRIPTION,
                data.serial_number,
                data.device_info,
            )
        ]
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
