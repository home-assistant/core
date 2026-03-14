"""Cover platform for INELNET Blinds."""

from __future__ import annotations

from typing import Any

from inelnet_api import InelnetChannel

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import InelnetConfigEntry
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one cover per channel. Each channel is one device; no group control."""
    data = entry.runtime_data
    clients = data.clients

    entities = [InelnetCoverEntity(entry, clients[ch]) for ch in data.channels]
    async_add_entities(entities)


class InelnetCoverEntity(CoverEntity):
    """One cover entity for a single channel. One device per channel."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, client: InelnetChannel) -> None:
        """Initialize the cover."""
        self._entry = entry
        self._client = client
        ch = client.channel
        self._attr_unique_id = f"{entry.entry_id}-ch{ch}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}-ch{ch}")},
            manufacturer="INELNET",
            model="Blinds controller",
            translation_key="channel",
            translation_placeholders={"channel": str(ch)},
        )

    @property
    def is_closed(self) -> bool | None:
        """State unknown – device does not report position."""
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (roll up)."""
        session = async_get_clientsession(self.hass)
        await self._client.up(session=session)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (roll down)."""
        session = async_get_clientsession(self.hass)
        await self._client.down(session=session)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        session = async_get_clientsession(self.hass)
        await self._client.stop(session=session)
