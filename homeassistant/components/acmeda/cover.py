"""Support for Acmeda Roller Blinds."""
import asyncio

import aiopulse

from homeassistant.components.cover import ATTR_POSITION, CoverDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import AcmedaBase
from .const import ACMEDA_HUB_UPDATE, DOMAIN, LOGGER
from .helpers import remove_devices


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Acmeda Rollers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.data["host"]]

    update_lock = asyncio.Lock()
    current = {}

    async def async_update():
        """Add any new covers."""
        async with update_lock:
            LOGGER.debug("Looking for new covers on: %s", hub.host)

            api = hub.api.rollers

            new_items = []

            for unique_id, roller in api.items():
                if unique_id not in current:
                    LOGGER.debug("New cover %s", unique_id)
                    new_item = AcmedaCover(hass, roller)
                    current[unique_id] = new_item
                    new_items.append(new_item)

            async_add_entities(new_items)

            removed_items = []
            for unique_id, element in current.items():
                if unique_id not in api:
                    LOGGER.debug("Removing cover %s", unique_id)
                    removed_items.append(element)

            for element in removed_items:
                del current[element.unique_id]

            await remove_devices(hass, config_entry, removed_items)

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
