"""Support for MotionMount sensors."""

import logging
import socket
from typing import TYPE_CHECKING

import motionmount

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CONNECTIONS, ATTR_IDENTIFIERS
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, EMPTY_MAC

_LOGGER = logging.getLogger(__name__)


class MotionMountEntity(Entity):
    """Representation of a MotionMount entity."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, mm: motionmount.MotionMount, config_entry: ConfigEntry) -> None:
        """Initialize general MotionMount entity."""
        self.mm = mm
        mac = format_mac(mm.mac.hex())

        # Create a base unique id
        if mac == EMPTY_MAC:
            self._base_unique_id = config_entry.entry_id
        else:
            self._base_unique_id = mac

        # Set device info
        self._attr_device_info = DeviceInfo(
            name=mm.name,
            manufacturer="Vogel's",
            model="MotionMount SIGNATURE Pro",
            model_id="TVM 7675 Pro",
        )

        if mac == EMPTY_MAC:
            self._attr_device_info[ATTR_IDENTIFIERS] = {(DOMAIN, config_entry.entry_id)}
        else:
            self._attr_device_info[ATTR_CONNECTIONS] = {
                (dr.CONNECTION_NETWORK_MAC, mac)
            }

    @property
    def available(self) -> bool:
        """Return True if the MotionMount is available (we're connected)."""
        return self.mm.is_connected

    def update_name(self) -> None:
        """Update the name of the associated device."""
        if TYPE_CHECKING:
            assert self.device_entry
        # Update the name in the device registry if needed
        if self.device_entry.name != self.mm.name:
            device_registry = dr.async_get(self.hass)
            device_registry.async_update_device(self.device_entry.id, name=self.mm.name)

    async def async_added_to_hass(self) -> None:
        """Store register state change callback."""
        self.mm.add_listener(self.async_write_ha_state)
        self.mm.add_listener(self.update_name)
        await super().async_added_to_hass()

    async def async_will_remove_from_hass(self) -> None:
        """Remove register state change callback."""
        self.mm.remove_listener(self.async_write_ha_state)
        self.mm.remove_listener(self.update_name)
        await super().async_will_remove_from_hass()

    async def _ensure_connected(self) -> bool:
        """Make sure there is a connection with the MotionMount.

        Returns false if the connection failed to be ensured.
        """

        if self.mm.is_connected:
            return True
        try:
            await self.mm.connect()
        except (ConnectionError, TimeoutError, socket.gaierror):
            # We're not interested in exceptions here. In case of a failed connection
            # the try/except from the caller will report it.
            # The purpose of `_ensure_connected()` is only to make sure we try to
            # reconnect, where failures should not be logged each time
            return False
        else:
            _LOGGER.warning("Successfully reconnected to MotionMount")
            return True
