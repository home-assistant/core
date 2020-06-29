"""Support for Z-Wave cover devices."""
import logging

from openzwavemqtt.const import CommandClass

from homeassistant.components.cover import (
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SUPPORT_CLOSE,
    SUPPORT_OPEN,
    SUPPORT_SET_POSITION,
    CoverEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)


SUPPORTED_FEATURES_POSITION = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Cover from Config Entry."""

    @callback
    def async_add_cover(values):
        """Add Z-Wave Cover."""

        if values.primary.command_class != CommandClass.SWITCH_MULTILEVEL:
            _LOGGER.warning("Cover not implemented for values %s", values.primary)
            return

        async_add_entities([ZWaveCoverEntity(values)])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{COVER_DOMAIN}", async_add_cover)
    )


class ZWaveCoverEntity(ZWaveDeviceEntity, CoverEntity):
    """Representation of a Z-Wave Cover device."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES_POSITION

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self.values.primary.value < 5

    @property
    def current_cover_position(self):
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        return self.values.primary.value

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.values.primary.send_value(kwargs[ATTR_POSITION])

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self.values.primary.send_value(99)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        self.values.primary.send_value(0)
