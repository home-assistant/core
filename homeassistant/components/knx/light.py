"""Support for KNX/IP lights."""
from xknx.devices import Light as XknxLight

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.core import callback
import homeassistant.util.color as color_util

from . import ATTR_DISCOVER_DEVICES, DATA_KNX

DEFAULT_COLOR = (0.0, 0.0)
DEFAULT_BRIGHTNESS = 255
DEFAULT_WHITE_VALUE = 255


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up lights for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up lights for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXLight(device))
    async_add_entities(entities)


class KNXLight(LightEntity):
    """Representation of a KNX light."""

    def __init__(self, device: XknxLight):
        """Initialize of KNX light."""
        self.device = device

        self._min_kelvin = device.min_kelvin
        self._max_kelvin = device.max_kelvin
        self._min_mireds = color_util.color_temperature_kelvin_to_mired(
            self._max_kelvin
        )
        self._max_mireds = color_util.color_temperature_kelvin_to_mired(
            self._min_kelvin
        )

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""

        async def after_update_callback(device):
            """Call after device was updated."""
            self.async_write_ha_state()

        self.device.register_device_updated_cb(after_update_callback)

    async def async_added_to_hass(self):
        """Store register state change callback."""
        self.async_register_callbacks()

    async def async_update(self):
        """Request a state update from KNX bus."""
        await self.device.sync()

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self.device.supports_brightness:
            return self.device.current_brightness
        hsv_color = self._hsv_color
        if self.device.supports_color and hsv_color:
            # pylint: disable=unsubscriptable-object
            return round(hsv_color[-1] / 100 * 255)
        return None

    @property
    def hs_color(self):
        """Return the HS color value."""
        rgb = None
        if self.device.supports_rgbw or self.device.supports_color:
            rgb, _ = self.device.current_color
        return color_util.color_RGB_to_hs(*rgb) if rgb else None

    @property
    def _hsv_color(self):
        """Return the HSV color value."""
        rgb = None
        if self.device.supports_rgbw or self.device.supports_color:
            rgb, _ = self.device.current_color
        return color_util.color_RGB_to_hsv(*rgb) if rgb else None

    @property
    def white_value(self):
        """Return the white value."""
        white = None
        if self.device.supports_rgbw:
            _, white = self.device.current_color
        return white

    @property
    def color_temp(self):
        """Return the color temperature in mireds."""
        if self.device.supports_color_temperature:
            kelvin = self.device.current_color_temperature
            if kelvin is not None:
                return color_util.color_temperature_kelvin_to_mired(kelvin)
        if self.device.supports_tunable_white:
            relative_ct = self.device.current_tunable_white
            if relative_ct is not None:
                # as KNX devices typically use Kelvin we use it as base for
                # calculating ct from percent
                return color_util.color_temperature_kelvin_to_mired(
                    self._min_kelvin
                    + ((relative_ct / 255) * (self._max_kelvin - self._min_kelvin))
                )
        return None

    @property
    def min_mireds(self):
        """Return the coldest color temp this light supports in mireds."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color temp this light supports in mireds."""
        return self._max_mireds

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_brightness:
            flags |= SUPPORT_BRIGHTNESS
        if self.device.supports_color:
            flags |= SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        if self.device.supports_rgbw:
            flags |= SUPPORT_COLOR | SUPPORT_WHITE_VALUE
        if self.device.supports_color_temperature or self.device.supports_tunable_white:
            flags |= SUPPORT_COLOR_TEMP
        return flags

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        hs_color = kwargs.get(ATTR_HS_COLOR, self.hs_color)
        white_value = kwargs.get(ATTR_WHITE_VALUE, self.white_value)
        mireds = kwargs.get(ATTR_COLOR_TEMP, self.color_temp)

        update_brightness = ATTR_BRIGHTNESS in kwargs
        update_color = ATTR_HS_COLOR in kwargs
        update_white_value = ATTR_WHITE_VALUE in kwargs
        update_color_temp = ATTR_COLOR_TEMP in kwargs

        # avoid conflicting changes and weird effects
        if not (
            self.is_on
            or update_brightness
            or update_color
            or update_white_value
            or update_color_temp
        ):
            await self.device.set_on()

        if self.device.supports_brightness and (update_brightness and not update_color):
            # if we don't need to update the color, try updating brightness
            # directly if supported; don't do it if color also has to be
            # changed, as RGB color implicitly sets the brightness as well
            await self.device.set_brightness(brightness)
        elif (self.device.supports_rgbw or self.device.supports_color) and (
            update_brightness or update_color or update_white_value
        ):
            # change RGB color, white value (if supported), and brightness
            # if brightness or hs_color was not yet set use the default value
            # to calculate RGB from as a fallback
            if brightness is None:
                brightness = DEFAULT_BRIGHTNESS
            if hs_color is None:
                hs_color = DEFAULT_COLOR
            if white_value is None and self.device.supports_rgbw:
                white_value = DEFAULT_WHITE_VALUE
            rgb = color_util.color_hsv_to_RGB(*hs_color, brightness * 100 / 255)
            await self.device.set_color(rgb, white_value)

        if update_color_temp:
            kelvin = int(color_util.color_temperature_mired_to_kelvin(mireds))
            kelvin = min(self._max_kelvin, max(self._min_kelvin, kelvin))

            if self.device.supports_color_temperature:
                await self.device.set_color_temperature(kelvin)
            elif self.device.supports_tunable_white:
                relative_ct = int(
                    255
                    * (kelvin - self._min_kelvin)
                    / (self._max_kelvin - self._min_kelvin)
                )
                await self.device.set_tunable_white(relative_ct)

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.device.set_off()
