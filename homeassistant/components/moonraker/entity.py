"""Moonrake API common entity definition."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .connector import APIConnector, generate_signal
from .const import DOMAIN, SIGNAL_STATE_AVAILABLE

_LOGGER = logging.getLogger(__name__)


class MoonrakerEntity(Entity):
    """Generic Moonraker entity (base class)."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        connector: APIConnector,
        desc: str | None,
    ) -> None:
        """Initialize the entity."""
        self.desc = desc
        self.entry = config_entry
        self.connector = connector
        self.module_available = False

    @property
    def name(self) -> str | None:
        """Return the name of the node."""
        return f"{self.entry.title.title()} {self.desc}"

    @property
    def should_poll(self) -> bool:
        """Push based integrations do not poll."""
        return False

    @property
    def unique_id(self) -> str:
        """Return the unique id based for the node."""
        uid = self.entry.unique_id or self.entry.entry_id
        return f"{uid}_{self.desc}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return info about the device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.entry.unique_id or self.entry.entry_id)},
            manufacturer="Moonraker",
            name=self.entry.title,
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available, False otherwise."""
        return super().available and self.module_available

    async def async_added_to_hass(self) -> None:
        """Configure entity update handlers."""

        @callback
        def update_availability(available: bool) -> None:
            """Entity state update."""
            self._attr_available = available
            self.async_write_ha_state()

        signal = generate_signal(SIGNAL_STATE_AVAILABLE, self.entry.entry_id)
        self.async_on_remove(
            async_dispatcher_connect(self.hass, signal, update_availability)
        )
