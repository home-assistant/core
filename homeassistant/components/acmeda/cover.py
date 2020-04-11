"""Support for Acmeda Roller Blinds."""
import asyncio

import aiopulse

from homeassistant.components.cover import ATTR_POSITION, CoverDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE
from .helpers import update_entities


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    update_lock = asyncio.Lock()
    current = {}

    async def async_update():
        async with update_lock:
            await update_entities(
                hass, AcmedaCover, config_entry, current, async_add_entities
            )

    async_dispatcher_connect(hass, ACMEDA_HUB_UPDATE, async_update)


class AcmedaCover(AcmedaBase, CoverDevice):
    """Representation of a Acmeda cover device."""

    def __init__(self, hass, roller: aiopulse.Roller):
        """Initialize the roller."""
        super().__init__(hass, roller)

    @property
    def current_cover_position(self):
        """Return the current position of the roller blind.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = 100 - self.roller.closed_percent
        return position

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        is_closed = self.roller.closed_percent == 100
        return is_closed

    async def close_cover(self, **kwargs):
        """Close the roller."""
        await self.roller.move_down()

    async def open_cover(self, **kwargs):
        """Open the roller."""
        await self.roller.move_up()

    async def stop_cover(self, **kwargs):
        """Stop the roller."""
        await self.roller.move_stop()

    async def set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        await self.roller.move_to(100 - kwargs[ATTR_POSITION])
