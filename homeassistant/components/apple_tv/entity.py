"""The Apple TV integration."""

from __future__ import annotations

from pyatv.interface import AppleTV as AppleTVInterface

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import AppleTVManager
from .const import DOMAIN, SIGNAL_CONNECTED, SIGNAL_DISCONNECTED


class AppleTVEntity(Entity):
    """Device that sends commands to an Apple TV."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None
    atv: AppleTVInterface | None = None

    def __init__(self, name: str, identifier: str, manager: AppleTVManager) -> None:
        """Initialize device."""
        self.manager = manager
        self._attr_unique_id = identifier
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            name=name,
        )

    async def async_added_to_hass(self) -> None:
        """Handle when an entity is about to be added to Home Assistant."""

        @callback
        def _async_connected(atv: AppleTVInterface) -> None:
            """Handle that a connection was made to a device."""
            self.atv = atv
            self.async_device_connected(atv)
            self.async_write_ha_state()

        @callback
        def _async_disconnected() -> None:
            """Handle that a connection to a device was lost."""
            self.async_device_disconnected()
            self.atv = None
            self.async_write_ha_state()

        if self.manager.atv:
            # ATV is already connected
            _async_connected(self.manager.atv)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{SIGNAL_CONNECTED}_{self.unique_id}", _async_connected
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_DISCONNECTED}_{self.unique_id}",
                _async_disconnected,
            )
        )

    def async_device_connected(self, atv: AppleTVInterface) -> None:
        """Handle when connection is made to device."""

    def async_device_disconnected(self) -> None:
        """Handle when connection was lost to device."""
