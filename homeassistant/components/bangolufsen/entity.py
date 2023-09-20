"""Entity representing a Bang & Olufsen device."""
from __future__ import annotations

from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from .const import CONNECTION_STATUS, DOMAIN, BangOlufsenVariables


class BangOlufsenEntity(Entity, BangOlufsenVariables):
    """Base Entity for BangOlufsen entities."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the object."""
        BangOlufsenVariables.__init__(self, entry)
        self._dispatchers: list[Callable] = []

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._unique_id)})
        self._attr_device_class = None
        self._attr_entity_category = None
        self._attr_should_poll = False

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        self._dispatchers = [
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{CONNECTION_STATUS}",
                self._update_connection_state,
            )
        ]

    async def async_will_remove_from_hass(self) -> None:
        """Turn off the dispatchers."""
        for dispatcher in self._dispatchers:
            dispatcher()

    async def _update_connection_state(self, connection_state: bool) -> None:
        """Update entity connection state."""
        self._attr_available = connection_state

        self.async_write_ha_state()
