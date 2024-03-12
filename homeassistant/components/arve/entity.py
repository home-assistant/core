"""Arve base entity."""

from __future__ import annotations

from asyncarve import Arve, ArveError

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .const import LOGGER


class ArveDeviceEntity(Entity):
    """Defines a base Arve device entity."""

    _attr_has_entity_name = True
    _attr_available = True

    def __init__(self, arve: Arve, entry: ConfigEntry) -> None:
        """Initialize the Arve device entity."""

        self._entry = entry
        self.arve = arve

    async def async_update(self) -> None:
        """Update Arve device entity."""
        if not self.enabled:
            return

        try:
            await self._arve_update()
            self._attr_available = True
        except ArveError:
            if self._attr_available:
                LOGGER.debug(
                    "An error occurred while updating Arve device", exc_info=True
                )
            self._attr_available = False

    async def _arve_update(self) -> None:
        """Update Arve device entity."""
        raise NotImplementedError()
