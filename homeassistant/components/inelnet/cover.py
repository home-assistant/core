"""Cover platform for INELNET Blinds."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

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
from .const import ACT_DOWN, ACT_STOP, ACT_UP, DEVICE_NAME_CHANNEL_TEMPLATE, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def send_command(hass: HomeAssistant, host: str, channel: int, act: int) -> bool:
    """Send REST command to a single channel. One channel per call, never broadcast."""
    url = f"http://{host}/msg.htm"
    payload = f"send_ch={channel}&send_act={act}"
    session = async_get_clientsession(hass)
    try:
        async with session.post(
            url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            return resp.status == 200
    except (aiohttp.ClientError, OSError) as e:
        _LOGGER.warning("INELNET command failed %s: %s", url, e)
        return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: InelnetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one cover per channel. Each channel is one device; no group control."""
    data = entry.runtime_data
    host = data.host
    channels = data.channels

    entities = [
        InelnetCoverEntity(entry, host, ch)  # one entity per channel, never all at once
        for ch in channels
    ]
    async_add_entities(entities)


class InelnetCoverEntity(CoverEntity):
    """One cover entity for a single channel. One device per channel; commands target this channel only."""

    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ConfigEntry, host: str, channel: int) -> None:
        """Initialize the cover."""
        self._entry = entry
        self._host = host
        self._channel = channel
        self._attr_unique_id = f"{entry.entry_id}-ch{channel}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}-ch{channel}")},
            name=DEVICE_NAME_CHANNEL_TEMPLATE.format(channel=channel),
            manufacturer="INELNET",
            model="Blinds controller",
        )

    @property
    def is_closed(self) -> bool | None:
        """State unknown – device does not report position."""
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover (roll up)."""
        await send_command(self.hass, self._host, self._channel, ACT_UP)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover (roll down)."""
        await send_command(self.hass, self._host, self._channel, ACT_DOWN)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await send_command(self.hass, self._host, self._channel, ACT_STOP)
