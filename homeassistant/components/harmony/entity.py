"""Base class Harmony entities."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_call_later

from .data import HarmonyData

_LOGGER = logging.getLogger(__name__)

TIME_MARK_DISCONNECTED = 10


class HarmonyEntity(Entity):
    """Base entity for Harmony with connection state handling."""

    _attr_has_entity_name = True

    def __init__(self, data: HarmonyData) -> None:
        """Initialize the Harmony base entity."""
        super().__init__()
        self._unsub_mark_disconnected: Callable[[], None] | None = None
        self._data = data
        self._attr_should_poll = False

    @property
    def available(self) -> bool:
        """Return True if we're connected to the Hub, otherwise False."""
        return self._data.available

    async def async_got_connected(self, _: str | None = None) -> None:
        """Notification that we're connected to the HUB."""
        _LOGGER.debug("%s: connected to the HUB", self._data.name)
        self.async_write_ha_state()

        self._async_clear_disconnection_delay()

    async def async_got_disconnected(self, _: str | None = None) -> None:
        """Notification that we're disconnected from the HUB."""
        _LOGGER.debug("%s: disconnected from the HUB", self._data.name)
        # We're going to wait for 10 seconds before announcing we're
        # unavailable, this to allow a reconnection to happen.
        self._unsub_mark_disconnected = async_call_later(
            self.hass,
            TIME_MARK_DISCONNECTED,
            self._async_mark_disconnected_if_unavailable,
        )

    @callback
    def _async_clear_disconnection_delay(self) -> None:
        if self._unsub_mark_disconnected:
            self._unsub_mark_disconnected()
            self._unsub_mark_disconnected = None

    @callback
    def _async_mark_disconnected_if_unavailable(self, _: datetime) -> None:
        self._unsub_mark_disconnected = None
        if not self.available:
            # Still disconnected. Let the state engine know.
            self.async_write_ha_state()
