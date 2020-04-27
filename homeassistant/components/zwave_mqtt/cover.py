"""Support for Z-Wave cover."""
import logging

from openzwavemqtt.const import CommandClass

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    SUPPORT_CLOSE,
    SUPPORT_CLOSE_TILT,
    SUPPORT_OPEN,
    SUPPORT_OPEN_TILT,
    SUPPORT_SET_POSITION,
    SUPPORT_SET_TILT_POSITION,
    CoverDevice,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import (
    DATA_UNSUBSCRIBE,
    DOMAIN,
    MANUFACTURER_ID_FIBARO,
    PRODUCT_TYPE_FIBARO_FGRM222,
)
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES_POSITION = SUPPORT_OPEN | SUPPORT_CLOSE | SUPPORT_SET_POSITION
SUPPORTED_FEATURES_TILT = (
    SUPPORT_OPEN_TILT | SUPPORT_CLOSE_TILT | SUPPORT_SET_TILT_POSITION
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Cover from Config Entry."""

    @callback
    def async_add_cover(values):
        """Add Z-Wave Cover."""
        # Specific Cover Types
        if values.primary.command_class != CommandClass.SWITCH_MULTILEVEL:
            _LOGGER.warning("Cover not implemented for values %s", values.primary)
            return

        if (
            values.primary.node.node_manufacturer_id == MANUFACTURER_ID_FIBARO
            and values.primary.node.node_product_type == PRODUCT_TYPE_FIBARO_FGRM222
        ):
            cover = FibaroFGRM222Cover(values)
        else:
            cover = ZWaveCover(values)

        async_add_entities([cover])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, "zwave_new_cover", async_add_cover)
    )

    await hass.data[DOMAIN][config_entry.entry_id]["mark_platform_loaded"]("cover")


class ZWaveCover(ZWaveDeviceEntity, CoverDevice):
    """Representation of a Z-Wave cover."""

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


class FibaroFGRM222Cover(ZWaveDeviceEntity, CoverDevice):
    """Representation of a Fibaro FGRM-222 cover."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_FEATURES_POSITION | SUPPORTED_FEATURES_TILT

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self.values.fgrm222_slat_position.value < 5

    @property
    def current_cover_position(self):
        """Return the current position of cover where 0 means closed and 100 is fully open."""
        return self.values.fgrm222_slat_position.value

    @property
    def current_cover_tilt_position(self):
        """Return the current tilt position of the cover where 0 means closed/no tilt and 100 means open/maximum tilt."""
        return self.values.fgrm222_tilt_position.value

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self.values.fgrm222_slat_position.send_value(99)
        self.values.fgrm222_tilt_position.send_value(99)

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        self.values.fgrm222_slat_position.send_value(0)
        self.values.fgrm222_tilt_position.send_value(0)

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        self.values.fgrm222_slat_position.send_value(kwargs[ATTR_POSITION])

    async def async_set_cover_tilt_position(self, **kwargs):
        """Move the cover tilt to a specific position."""
        self.values.fgrm222_tilt_position.send_value(kwargs[ATTR_TILT_POSITION])

    async def async_open_cover_tilt(self, **kwargs):
        """Open the cover tilt."""
        self.values.fgrm222_tilt_position.send_value(99)

    async def async_close_cover_tilt(self, **kwargs):
        """Close the cover tilt."""
        self.values.fgrm222_tilt_position.send_value(0)
