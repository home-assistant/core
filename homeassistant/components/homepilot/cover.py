"""Support for HomePilot Covers."""

import asyncio

from pyhomepilot.devices import Blind
from pyhomepilot.utils import reverse_percentage

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_BLIND,
    DEVICE_CLASS_DOOR,
    DEVICE_CLASS_GARAGE,
    DEVICE_CLASS_SHADE,
    DEVICE_CLASS_WINDOW,
    CoverEntity,
)

from .const import DOMAIN, STOP_UPDATE_DELAY
from .entity import HomePilotEntity

# supported device classes based on selected icon set
DEVICE_CLASSES = {
    "iconset6": DEVICE_CLASS_BLIND,
    "iconset7": DEVICE_CLASS_SHADE,
    "iconset8": DEVICE_CLASS_SHADE,
    "iconset9": DEVICE_CLASS_DOOR,
    "iconset12": DEVICE_CLASS_DOOR,
    "iconset14": DEVICE_CLASS_DOOR,
    "iconset15": DEVICE_CLASS_SHADE,
    "iconset20": DEVICE_CLASS_BLIND,
    "iconset24": DEVICE_CLASS_WINDOW,
    "iconset30": DEVICE_CLASS_GARAGE,
    "iconset31": DEVICE_CLASS_GARAGE,
    "iconset34": DEVICE_CLASS_WINDOW,
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up HomePilot cover platform."""

    instance = hass.data[DOMAIN][config_entry.entry_id]

    entities = []
    for uid, device in instance["coordinator"].data.items():
        if isinstance(device, Blind):
            entities.append(HomePilotCoverEntity(instance, uid))

    async_add_entities(entities)


class HomePilotCoverEntity(HomePilotEntity, CoverEntity):
    """Class representing HomePilot cover."""

    @property
    def device_class(self):
        """Return the class of the device."""
        return DEVICE_CLASSES.get(self._device.iconSet["k"])

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._device.position == 100

    @property
    def current_cover_position(self):
        """Return the position of the cover from 0 to 100."""
        return reverse_percentage(self._device.position)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._device.async_move_up()
        await self.coordinator.async_refresh()

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._device.async_move_down()
        await self.coordinator.async_refresh()

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        position = kwargs[ATTR_POSITION]
        await self._device.async_goto_position(reverse_percentage(position))
        await self.coordinator.async_refresh()

    async def async_stop_cover(self, **kwargs):
        """Stop the cover."""
        await self._device.async_stop()
        await asyncio.sleep(STOP_UPDATE_DELAY)
        await self.coordinator.async_refresh()
