"""Support for Z-Wave lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ATTR_WHITE_VALUE,
    DOMAIN as LIGHT_DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
import homeassistant.util.color as color_util

from .const import DATA_UNSUBSCRIBE, DOMAIN
from .entity import ZWaveDeviceEntity

_LOGGER = logging.getLogger(__name__)

ATTR_VALUE = "Value"
COLOR_CHANNEL_WARM_WHITE = 0x01
COLOR_CHANNEL_COLD_WHITE = 0x02
COLOR_CHANNEL_RED = 0x04
COLOR_CHANNEL_GREEN = 0x08
COLOR_CHANNEL_BLUE = 0x10


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Z-Wave Light from Config Entry."""

    @callback
    def async_add_light(values):
        """Add Z-Wave Light."""
        light = ZwaveLight(values)

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


class ZwaveLight(ZWaveDeviceEntity, LightEntity):
    """Representation of a Z-Wave light."""

    def __init__(self, values):
        """Initialize the light."""
        super().__init__(values)
        self._color_channels = None
        self._hs = None
        self._white = None
        self._ct = None
        self._supported_features = SUPPORT_BRIGHTNESS
        self._min_mireds = 153  # 6500K as a safe default
        self._max_mireds = 370  # 2700K as a safe default

        # make sure that supported features is correctly set
        self.on_value_update()

    @callback
    def on_value_update(self):
        """Call when the underlying value(s) is added or updated."""
        if self.values.dimming_duration is not None:
            self._supported_features |= SUPPORT_TRANSITION

        if self.values.color is not None:
            self._supported_features |= SUPPORT_COLOR

        if self.values.color_channels is not None:
            # Support Color Temp if both white channels
            if (self.values.color_channels.value & COLOR_CHANNEL_WARM_WHITE) and (
                self.values.color_channels.value & COLOR_CHANNEL_COLD_WHITE
            ):
                self._supported_features |= SUPPORT_COLOR_TEMP

            # Support White value if only a single white channel
            if ((self.values.color_channels.value & COLOR_CHANNEL_WARM_WHITE) != 0) ^ (
                (self.values.color_channels.value & COLOR_CHANNEL_COLD_WHITE) != 0
            ):
                self._supported_features |= SUPPORT_WHITE_VALUE

        if self.values.color is not None:
            self._calculate_color_values()

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

    @property
    def hs_color(self):
        """Return the hs color."""
        return self._hs

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._ct

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._max_mireds

    @callback
    def async_set_duration(self, **kwargs):
        """Set the transition time for the brightness value.

        Zwave Dimming Duration values now use seconds as an
        integer (max: 7620 seconds or 127 mins)
        Build 1205 https://github.com/OpenZWave/open-zwave/commit/f81bc04
        """
        if self.values.dimming_duration is None:
            return

        ozw_version = tuple(
            int(x)
            for x in self.values.primary.ozw_instance.get_status().openzwave_version.split(
                "."
            )
        )

        if ATTR_TRANSITION not in kwargs:
            # no transition specified by user, use defaults
            new_value = 7621  # anything over 7620 uses the factory default
            if ozw_version < (1, 6, 1205):
                new_value = 255  # default for older version

        else:
            # transition specified by user
            new_value = int(max(0, min(7620, kwargs[ATTR_TRANSITION])))
            if ozw_version < (1, 6, 1205):
                transition = kwargs[ATTR_TRANSITION]
                if transition <= 127:
                    new_value = int(transition)
                else:
                    minutes = int(transition / 60)
                    _LOGGER.debug(
                        "Transition rounded to %d minutes for %s",
                        minutes,
                        self.entity_id,
                    )
                    new_value = minutes + 128

        # only send value if it differs from current
        # this prevents a command for nothing
        if self.values.dimming_duration.value != new_value:
            self.values.dimming_duration.send_value(new_value)

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self.async_set_duration(**kwargs)

        rgbw = None
        white = kwargs.get(ATTR_WHITE_VALUE)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        color_temp = kwargs.get(ATTR_COLOR_TEMP)

        if hs_color is not None:
            rgbw = "#"
            for colorval in color_util.color_hs_to_RGB(*hs_color):
                rgbw += f"{colorval:02x}"
            if self._color_channels and self._color_channels & COLOR_CHANNEL_COLD_WHITE:
                rgbw += "0000"
            else:
                # trim the CW value or it will not work correctly
                rgbw += "00"
            # white LED must be off in order for color to work

        elif white is not None:
            if self._color_channels & COLOR_CHANNEL_WARM_WHITE:
                # trim the CW value or it will not work correctly
                rgbw = f"#000000{white:02x}"
            else:
                rgbw = f"#00000000{white:02x}"

        elif color_temp is not None:
            # Limit color temp to min/max values
            cold = max(
                0,
                min(
                    255,
                    round(
                        (self._max_mireds - color_temp)
                        / (self._max_mireds - self._min_mireds)
                        * 255
                    ),
                ),
            )
            warm = 255 - cold
            rgbw = f"#000000{warm:02x}{cold:02x}"

        if rgbw and self.values.color:
            self.values.color.send_value(rgbw)

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

    def _calculate_color_values(self):
        """Parse color rgb and color temperature data."""
        # Color Data String
        data = self.values.color.data[ATTR_VALUE]

        # RGB is always present in the OpenZWave color data string.
        rgb = [int(data[1:3], 16), int(data[3:5], 16), int(data[5:7], 16)]
        self._hs = color_util.color_RGB_to_hs(*rgb)

        if self.values.color_channels is None:
            return

        # Color Channels
        self._color_channels = self.values.color_channels.data[ATTR_VALUE]

        # Parse remaining color channels. OpenZWave appends white channels
        # that are present.
        index = 7
        temp_warm = 0
        temp_cold = 0

        # Update color temp limits.
        if self.values.min_kelvin:
            self._max_mireds = color_util.color_temperature_kelvin_to_mired(
                self.values.min_kelvin.data[ATTR_VALUE]
            )
        if self.values.max_kelvin:
            self._min_mireds = color_util.color_temperature_kelvin_to_mired(
                self.values.max_kelvin.data[ATTR_VALUE]
            )

        # Warm white
        if self._color_channels & COLOR_CHANNEL_WARM_WHITE:
            self._white = int(data[index : index + 2], 16)
            temp_warm = self._white

        index += 2

        # Cold white
        if self._color_channels & COLOR_CHANNEL_COLD_WHITE:
            self._white = int(data[index : index + 2], 16)
            temp_cold = self._white

        # Calculate color temps based on white LED status
        if temp_cold or temp_warm:
            self._ct = round(
                self._max_mireds
                - ((temp_cold / 255) * (self._max_mireds - self._min_mireds))
            )

        if not (
            self._color_channels & COLOR_CHANNEL_RED
            or self._color_channels & COLOR_CHANNEL_GREEN
            or self._color_channels & COLOR_CHANNEL_BLUE
        ):
            self._hs = None
