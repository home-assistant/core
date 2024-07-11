"""Control binary sensor instances."""

import asyncio
from datetime import timedelta
import logging

from ProgettiHWSW.input import Input

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import setup_input
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensors from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    input_count = config_entry.data["input_count"]

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        async with asyncio.timeout(5):
            return await board_api.get_inputs()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="binary_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC),
    )
    await coordinator.async_refresh()

    async_add_entities(
        ProgettihwswBinarySensor(
            coordinator,
            f"Input #{i}",
            setup_input(board_api, i),
        )
        for i in range(1, int(input_count) + 1)
    )


class ProgettihwswBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represent a binary sensor."""

    def __init__(self, coordinator, name, sensor: Input) -> None:
        """Set initializing values."""
        super().__init__(coordinator)
        self._attr_name = name
        self._sensor = sensor

    @property
    def is_on(self):
        """Get sensor state."""
        return self.coordinator.data[self._sensor.id]
