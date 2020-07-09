"""Support for the RPi Pimoroni Fan Shim LED."""
from homeassistant.components.light import ATTR_HS_COLOR, SUPPORT_COLOR, LightEntity
import homeassistant.util.color as color_util

from .const import DOMAIN


async def async_setup_entry(
    hass, config_entry, async_add_entities, discovery_info=None
):
    """Set up the light platform."""
    fanshim = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([FanShimLightEntity(fanshim)])


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the light platform."""
    fanshim = hass.data[DOMAIN]
    add_entities([FanShimLightEntity(fanshim)])


class FanShimLightEntity(LightEntity):
    """Fan Shim LED Device."""

    def __init__(self, fanshim):
        """Initialize the Light."""

        self._name = "Fan Shim LED"
        self._state = None
        self._fanshim = fanshim
        self._color = (255, 255, 255)

        # Switch off LED
        self._fanshim.hub.set_light(0, 0, 0)
        self._state = False

    @property
    def name(self):
        """Return the name."""
        return "Fan Shim LED"

    @property
    def is_on(self):
        """Return the state."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_COLOR

    def turn_on(self, **kwargs):
        """Turn on LED."""
        if ATTR_HS_COLOR in kwargs:
            self._color = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])

        self._fanshim.hub.set_light(*self._color)
        self._state = True

    def turn_off(self, **kwargs):
        """Turn off LED."""
        self._fanshim.hub.set_light(0, 0, 0)
        self._state = False
