"""Generic platform."""
from __future__ import annotations

import logging
from typing import Callable

from devolo_plc_api.device import Device

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, TOPIC_UPDATE

_LOGGER = logging.getLogger(__name__)


class DevoloDevice(Entity):
    """Representation of a devolo home network device."""

    def __init__(self, device: Device, device_name: str) -> None:
        """Initialize a devolo home network device."""
        self._enabled_default: bool
        self._icon: str
        self._name: str
        self._unique_id: str

        self._available = True
        self._device = device
        self._dispatcher_disconnect: Callable | None = None
        self._state = 0
        self._device_name = device_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.serial_number)},
            "manufacturer": "devolo",
            "model": self._device.product,
            "name": self._device_name,
            "sw_version": self._device.firmware_version,
        }

    @property
    def available(self) -> bool:
        """Return the online state."""
        return self._available

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self._enabled_default

    @property
    def icon(self) -> str:
        """Return icon."""
        return self._icon

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the device."""
        return self._state

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the entity."""
        return self._unique_id

    async def async_added_to_hass(self) -> None:
        """Register dispatcher when added."""

        @callback
        def update():
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._dispatcher_disconnect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher listener when removed."""
        if self._dispatcher_disconnect:
            self._dispatcher_disconnect()

    def _set_availability(self, available: bool) -> None:
        """Set availability and log if changed."""
        if self._available and not available:
            _LOGGER.warning("Unable to connect to %s", self._device_name)
        if not self._available and available:
            _LOGGER.warning("Reconnected to %s", self._device_name)
        self._available = available
