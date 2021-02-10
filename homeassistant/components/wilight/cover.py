"""Support for WiLight Cover."""

from pywilight.const import (
    COVER_V1,
    DOMAIN,
    ITEM_COVER,
    WL_CLOSE,
    WL_CLOSING,
    WL_OPEN,
    WL_OPENING,
    WL_STOP,
    WL_STOPPED,
)

from homeassistant.components.cover import ATTR_POSITION, CoverEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import WiLightDevice


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    """Set up WiLight covers from a config entry."""
    parent = hass.data[DOMAIN][entry.entry_id]

    # Handle a discovered WiLight device.
    entities = []
    for item in parent.api.items:
        if item["type"] != ITEM_COVER:
            continue
        index = item["index"]
        item_name = item["name"]
        if item["sub_type"] != COVER_V1:
            continue
        entity = WiLightCover(parent.api, index, item_name)
        entities.append(entity)

    async_add_entities(entities)


def wilight_to_hass_position(value):
    """Convert wilight position 1..255 to hass format 0..100."""
    return min(100, round((value * 100) / 255))


def hass_to_wilight_position(value):
    """Convert hass position 0..100 to wilight 1..255 scale."""
    return min(255, round((value * 255) / 100))


class WiLightCover(WiLightDevice, CoverEntity):
    """Representation of a WiLights cover."""

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        if "position_current" in self._status:
            return wilight_to_hass_position(self._status["position_current"])
        return None

    @property
    def is_opening(self):
        """Return if the cover is opening or not."""
        if "motor_state" not in self._status:
            return None
        return self._status["motor_state"] == WL_OPENING

    @property
    def is_closing(self):
        """Return if the cover is closing or not."""
        if "motor_state" not in self._status:
            return None
        return self._status["motor_state"] == WL_CLOSING

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        if "motor_state" not in self._status or "position_current" not in self._status:
            return None
        return (
            self._status["motor_state"] == WL_STOPPED
            and wilight_to_hass_position(self._status["position_current"]) == 0
        )

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._client.cover_command(self._index, WL_OPEN)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._client.cover_command(self._index, WL_CLOSE)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = hass_to_wilight_position(kwargs[ATTR_POSITION])
        await self._client.set_cover_position(self._index, position)

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._client.cover_command(self._index, WL_STOP)
