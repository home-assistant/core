"""Support for Z-Wave cover devices."""
import logging
from typing import Any, Callable, List, Optional

from zwave_js_server.client import Client as ZwaveClient

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    CoverEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_CLIENT, DATA_UNSUBSCRIBE, DOMAIN
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity

LOGGER = logging.getLogger(__name__)
SUPPORT_GARAGE = SUPPORT_OPEN | SUPPORT_CLOSE


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Callable
) -> None:
    """Set up Z-Wave Cover from Config Entry."""
    client: ZwaveClient = hass.data[DOMAIN][config_entry.entry_id][DATA_CLIENT]

    @callback
    def async_add_cover(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave cover."""
        entities: List[ZWaveBaseEntity] = []
        entities.append(ZWaveCover(config_entry, client, info))
        async_add_entities(entities)

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{config_entry.entry_id}_add_{COVER_DOMAIN}",
            async_add_cover,
        )
    )


def percent_to_zwave_position(value: int) -> int:
    """Convert position in 0-100 scale to 0-99 scale.

    `value` -- (int) Position byte value from 0-100.
    """
    if value > 0:
        return max(1, round((value / 100) * 99))
    return 0


class ZWaveCover(ZWaveBaseEntity, CoverEntity):
    """Representation of a Z-Wave Cover device."""

    @property
    def is_closed(self) -> Optional[bool]:
        """Return true if cover is closed."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return bool(self.info.primary_value.value == 0)

    @property
    def current_cover_position(self) -> Optional[int]:
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        if self.info.primary_value.value is None:
            # guard missing value
            return None
        return round((self.info.primary_value.value / 99) * 100)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(
            target_value, percent_to_zwave_position(kwargs[ATTR_POSITION])
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 99)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        target_value = self.get_zwave_value("targetValue")
        await self.info.node.async_set_value(target_value, 0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        target_value = self.get_zwave_value("Open") or self.get_zwave_value("Up")
        if target_value:
            await self.info.node.async_set_value(target_value, False)
        target_value = self.get_zwave_value("Close") or self.get_zwave_value("Down")
        if target_value:
            await self.info.node.async_set_value(target_value, False)
