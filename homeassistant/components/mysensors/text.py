"""Provide a text platform for MySensors."""
from __future__ import annotations

from homeassistant.components.text import TextEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .. import mysensors
from .const import MYSENSORS_DISCOVERY, DiscoveryInfo
from .device import MySensorsEntity
from .helpers import on_unload


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up this platform for a specific ConfigEntry(==Gateway)."""

    @callback
    def async_discover(discovery_info: DiscoveryInfo) -> None:
        """Discover and add a MySensors text entity."""
        mysensors.setup_mysensors_platform(
            hass,
            Platform.TEXT,
            discovery_info,
            MySensorsText,
            async_add_entities=async_add_entities,
        )

    on_unload(
        hass,
        config_entry.entry_id,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, Platform.TEXT),
            async_discover,
        ),
    )


class MySensorsText(MySensorsEntity, TextEntity):
    """Representation of the value of a MySensors Text child node."""

    _attr_native_max = 25

    @property
    def native_value(self) -> str | None:
        """Return the value reported by the text."""
        return self._values.get(self.value_type)

    async def async_set_value(self, value: str) -> None:
        """Change the value."""
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, value, ack=1
        )
