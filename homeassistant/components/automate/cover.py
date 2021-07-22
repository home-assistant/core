"""Support for Automate Roller Blinds."""
import aiopulse2

from homeassistant.components.cover import (
    ATTR_POSITION,
    DEVICE_CLASS_SHADE,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    SUPPORT_STOP,
    SUPPORT_STOP_TILT,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .base import AutomateBase
from .const import AUTOMATE_HUB_UPDATE, DOMAIN
from .helpers import async_add_automate_entities


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Automate Rollers from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]

    current = set()

    @callback
    def async_add_automate_covers():
        async_add_automate_entities(
            hass, AutomateCover, config_entry, current, async_add_entities
        )

    hub.cleanup_callbacks.append(
        async_dispatcher_connect(
            hass,
            AUTOMATE_HUB_UPDATE.format(config_entry.entry_id),
            async_add_automate_covers,
        )
    )


class AutomateCover(AutomateBase, CoverEntity):
    """Representation of a Automate cover device."""

    @property
    def current_cover_position(self):
        """Return the current position of the roller blind.

        None is unknown, 0 is closed, 100 is fully open.
        """
        position = None
        if self.roller.closed_percent is not None:
            position = 100 - self.roller.closed_percent
        return position

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt of the roller blind.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return None

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = 0
        if self.current_cover_position is not None:
            supported_features |= (
                SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_STOP | SUPPORT_SET_POSITION
            )
        if self.current_cover_tilt_position is not None:
            supported_features |= (
                SUPPORT_OPEN_TILT
                | SUPPORT_CLOSE_TILT
                | SUPPORT_STOP_TILT
                | SUPPORT_SET_TILT_POSITION
            )

        return supported_features

    @property
    def device_info(self):
        """Return the device info."""
        attrs = super().device_info
        attrs["manufacturer"] = "Automate"
        attrs["model"] = self.roller.devicetype
        attrs["sw_version"] = self.roller.version
        attrs["via_device"] = (DOMAIN, self.roller.hub.id)
        attrs["name"] = self.name
        return attrs

    @property
    def device_class(self):
        """Class of the cover, a shade."""
        return DEVICE_CLASS_SHADE

    @property
    def is_opening(self):
        """Is cover opening/moving up."""
        return self.roller.action == aiopulse2.MovingAction.up

    @property
    def is_closing(self):
        """Is cover closing/moving down."""
        return self.roller.action == aiopulse2.MovingAction.down

    @property
    def is_closed(self):
        """Return if the cover is closed."""
        return self.roller.closed_percent == 100

    async def async_close_cover(self, **kwargs):
        """Close the roller."""
        await self.roller.move_down()

    async def async_open_cover(self, **kwargs):
        """Open the roller."""
        await self.roller.move_up()

    async def async_stop_cover(self, **kwargs):
        """Stop the roller."""
        await self.roller.move_stop()

    async def async_set_cover_position(self, **kwargs):
        """Move the roller shutter to a specific position."""
        await self.roller.move_to(100 - kwargs[ATTR_POSITION])

    async def async_close_cover_tilt(self, **kwargs):
        """Close the roller."""
        await self.roller.move_down()

    async def async_open_cover_tilt(self, **kwargs):
        """Open the roller."""
        await self.roller.move_up()

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop the roller."""
        await self.roller.move_stop()

    async def async_set_cover_tilt(self, **kwargs):
        """Tilt the roller shutter to a specific position."""
        await self.roller.move_to(100 - kwargs[ATTR_POSITION])
