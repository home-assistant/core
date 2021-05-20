"""Base implementation for all modbus platforms."""
from __future__ import annotations

from abc import abstractmethod
from datetime import timedelta
import logging
from typing import Any

from homeassistant.const import (
    CONF_ADDRESS,
    CONF_DEVICE_CLASS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_INPUT_TYPE
from .modbus import ModbusHub

PARALLEL_UPDATES = 1
_LOGGER = logging.getLogger(__name__)


class BasePlatform(Entity):
    """Base for readonly platforms."""

    def __init__(self, hub: ModbusHub, entry: dict[str, Any]) -> None:
        """Initialize the Modbus binary sensor."""
        self._hub = hub
        self._name = entry[CONF_NAME]
        self._slave = entry.get(CONF_SLAVE)
        self._address = int(entry[CONF_ADDRESS])
        self._device_class = entry.get(CONF_DEVICE_CLASS)
        self._input_type = entry[CONF_INPUT_TYPE]
        self._value = None
        self._available = True
        self._scan_interval = timedelta(seconds=entry[CONF_SCAN_INTERVAL])

    @abstractmethod
    async def async_update(self, now=None):
        """Virtual function to be overwritten."""

    async def async_base_added_to_hass(self):
        """Handle entity which will be added."""
        async_track_time_interval(self.hass, self.async_update, self._scan_interval)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def device_class(self) -> str | None:
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available
