"""Support for Z-Wave lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Light from Config Entry."""

    @callback
    def async_add_light(values):
        """Add Z-Wave Light."""
        light = ZwaveDimmer(values)
        async_add_entities([light])

    hass.data[DOMAIN][config_entry.entry_id][DATA_UNSUBSCRIBE].append(
        async_dispatcher_connect(hass, f"{DOMAIN}_new_{LIGHT_DOMAIN}", async_add_light)
    )


def byte_to_zwave_brightness(value):
    """Convert brightness in 0-255 scale to 0-99 scale.

    `value` -- (int) Brightness byte value from 0-255.
    """
    if value > 0:
        return max(1, round((value / 255) * 99))
    return 0


class ZwaveDimmer(ZWaveDeviceEntity, LightEntity):
    """Representation of a Z-Wave dimmer."""

    def __init__(self, values):
        """Initialize the light."""
        super().__init__(values)
        self._supported_features = SUPPORT_BRIGHTNESS
        # make sure that supported features is correctly set
        self.on_value_update()

    @callback
    def on_value_update(self):
        """Call when the underlying value(s) is added or updated."""
        self._supported_features = SUPPORT_BRIGHTNESS
        if self.values.dimming_duration is not None:
            self._supported_features |= SUPPORT_TRANSITION

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255.

        Zwave multilevel switches use a range of [0, 99] to control brightness.
        """
        if "target" in self.values:
            return round((self.values.target.value / 99) * 255)
        return round((self.values.primary.value / 99) * 255)

    @property
    def is_on(self):
        """Return true if device is on (brightness above 0)."""
        if "target" in self.values:
            return self.values.target.value > 0
        return self.values.primary.value > 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._supported_features

    @callback
    def async_set_duration(self, **kwargs):
        """Set the transition time for the brightness value.

        Zwave Dimming Duration values:
        0       = instant
        0-127   = 1 second to 127 seconds
        128-254 = 1 minute to 127 minutes
        255     = factory default
        """
        if self.values.dimming_duration is None:
            return

        if ATTR_TRANSITION not in kwargs:
            # no transition specified by user, use defaults
            new_value = 255
        else:
            # transition specified by user, convert to zwave value
            transition = kwargs[ATTR_TRANSITION]
            if transition <= 127:
                new_value = int(transition)
            else:
                minutes = int(transition / 60)
                _LOGGER.debug(
                    "Transition rounded to %d minutes for %s", minutes, self.entity_id
                )
                new_value = minutes + 128

        # only send value if it differs from current
        # this prevents a command for nothing
        if self.values.dimming_duration.value != new_value:
            self.values.dimming_duration.send_value(new_value)

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self.async_set_duration(**kwargs)

        # Zwave multilevel switches use a range of [0, 99] to control
        # brightness. Level 255 means to set it to previous value.
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            brightness = byte_to_zwave_brightness(brightness)
        else:
            brightness = 255

        self.values.primary.send_value(brightness)

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        self.async_set_duration(**kwargs)

        self.values.primary.send_value(0)
