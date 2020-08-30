"""Control binary sensor instances."""

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


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set the progettihwsw platform up and create sensor instances (legacy)."""

    return True


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the binary sensors from a config entry."""
    board_api = hass.data[DOMAIN][config_entry.entry_id]
    input_count = config_entry.data["input_count"]
    binary_sensors = []

    async def async_update_data():
        """Fetch data from API endpoint of board."""
        async with async_timeout.timeout(5):
            return await board_api.get_inputs()

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="binary_sensor",
        update_method=async_update_data,
        update_interval=timedelta(seconds=DEFAULT_POLLING_INTERVAL_SEC),
    )
    await coordinator.async_refresh()

    for i in range(1, int(input_count) + 1):
        binary_sensors.append(
            ProgettihwswBinarySensor(
                hass,
                coordinator,
                config_entry,
                f"Input #{i}",
                setup_input(board_api, i),
            )
        )

    async_add_entities(binary_sensors)


class ProgettihwswBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Represent a binary sensor."""

    def __init__(self, hass, coordinator, config_entry, name, sensor: Input):
        """Set initializing values."""
        super().__init__(coordinator)
        self._name = name
        self._sensor = sensor

    @property
    def name(self):
        """Return the sensor name."""
        return self._name

    @property
    def is_on(self):
        """Get sensor state."""
        return self.coordinator.data[self._sensor.id]
