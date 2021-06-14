"""Control binary sensor instances."""

import asyncio
from datetime import timedelta
import logging

from ProgettiHWSW.input import Input
import async_timeout

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import setup_input
from .const import DEFAULT_POLLING_INTERVAL_SEC, DOMAIN

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the binary sensors from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    inputs = config_entry.data["inputs"]
    binary_sensors = []

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        try:
            async with async_timeout.timeout(5):
                return await board_api.get_inputs()
        except asyncio.TimeoutError:
            return False

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="binary_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC),
    )
    await coordinator.async_refresh()

    for i in inputs:
        binary_sensors.append(
            ProgettihwswBinarySensor(
                coordinator,
                f"Input #{i}",
                board_api.create_unique_id(i, "input"),
                setup_input(board_api, i),
            )
        )

    async_add_entities(binary_sensors)


class ProgettihwswBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represent a binary sensor."""

    def __init__(self, coordinator, name, unique_id, sensor: Input):
        """Set initializing values."""
        super().__init__(coordinator)
        self._name = name
        self._sensor = sensor
        self._unique_id = unique_id

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def unique_id(self):
        """Return a base64 encoded unique id number."""
        return self._unique_id

    @property
    def is_on(self):
        """Get sensor state."""
        if self.coordinator.data is False:
            return False

        return self.coordinator.data[str(self._sensor.id)]
