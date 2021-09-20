"""Support for MySensors lights."""
from homeassistant.components import mysensors
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_WHITE_VALUE,
    DOMAIN,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_WHITE_VALUE,
    LightEntity,
)
from homeassistant.components.mysensors import on_unload
from homeassistant.components.mysensors.const import MYSENSORS_DISCOVERY
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.color as color_util
from homeassistant.util.color import rgb_hex_to_rgb_list

SUPPORT_MYSENSORS_RGBW = SUPPORT_COLOR | SUPPORT_WHITE_VALUE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up this platform for a specific ConfigEntry(==Gateway)."""
    device_class_map = {
        "S_DIMMER": MySensorsLightDimmer,
        "S_RGB_LIGHT": MySensorsLightRGB,
        "S_RGBW_LIGHT": MySensorsLightRGBW,
    }

    async def async_discover(discovery_info):
        """Discover and add a MySensors light."""
        mysensors.setup_mysensors_platform(
            hass,
            DOMAIN,
            discovery_info,
            device_class_map,
            async_add_entities=async_add_entities,
        )

    await on_unload(
        hass,
        config_entry,
        async_dispatcher_connect(
            hass,
            MYSENSORS_DISCOVERY.format(config_entry.entry_id, DOMAIN),
            async_discover,
        ),
    )


class MySensorsLight(mysensors.device.MySensorsEntity, LightEntity):
    """Representation of a MySensors Light child node."""

    def __init__(self, *args):
        """Initialize a MySensors Light."""
        super().__init__(*args)
        self._state = None
        self._brightness = None
        self._hs = None
        self._white = None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the hs color value [int, int]."""
        return self._hs

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def _turn_on_light(self):
        """Turn on light child device."""
        set_req = self.gateway.const.SetReq

        if self._state:
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1, ack=1
        )

        if self.assumed_state:
            # optimistically assume that light has changed state
            self._state = True
            self._values[set_req.V_LIGHT] = STATE_ON

    def _turn_on_dimmer(self, **kwargs):
        """Turn on dimmer child device."""
        set_req = self.gateway.const.SetReq
        brightness = self._brightness

        if (
            ATTR_BRIGHTNESS not in kwargs
            or kwargs[ATTR_BRIGHTNESS] == self._brightness
            or set_req.V_DIMMER not in self._values
        ):
            return
        brightness = kwargs[ATTR_BRIGHTNESS]
        percent = round(100 * brightness / 255)
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DIMMER, percent, ack=1
        )

        if self.assumed_state:
            # optimistically assume that light has changed state
            self._brightness = brightness
            self._values[set_req.V_DIMMER] = percent

    def _turn_on_rgb_and_w(self, hex_template, **kwargs):
        """Turn on RGB or RGBW child device."""
        rgb = list(color_util.color_hs_to_RGB(*self._hs))
        white = self._white
        hex_color = self._values.get(self.value_type)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        if hs_color is not None:
            new_rgb = color_util.color_hs_to_RGB(*hs_color)
        else:
            new_rgb = None
        new_white = kwargs.get(ATTR_WHITE_VALUE)

        if new_rgb is None and new_white is None:
            return
        if new_rgb is not None:
            rgb = list(new_rgb)
        if hex_template == "%02x%02x%02x%02x":
            if new_white is not None:
                rgb.append(new_white)
            else:
                rgb.append(white)
        hex_color = hex_template % tuple(rgb)
        if len(rgb) > 3:
            white = rgb.pop()
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, hex_color, ack=1
        )

        if self.assumed_state:
            # optimistically assume that light has changed state
            self._hs = color_util.color_RGB_to_hs(*rgb)
            self._white = white
            self._values[self.value_type] = hex_color

    async def async_turn_off(self, **kwargs):
        """Turn the device off."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self.gateway.set_child_value(self.node_id, self.child_id, value_type, 0, ack=1)
        if self.assumed_state:
            # optimistically assume that light has changed state
            self._state = False
            self._values[value_type] = STATE_OFF
            self.async_write_ha_state()

    @callback
    def _async_update_light(self):
        """Update the controller with values from light child."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self._state = self._values[value_type] == STATE_ON

    @callback
    def _async_update_dimmer(self):
        """Update the controller with values from dimmer child."""
        value_type = self.gateway.const.SetReq.V_DIMMER
        if value_type in self._values:
            self._brightness = round(255 * int(self._values[value_type]) / 100)
            if self._brightness == 0:
                self._state = False

    @callback
    def _async_update_rgb_or_w(self):
        """Update the controller with values from RGB or RGBW child."""
        value = self._values[self.value_type]
        color_list = rgb_hex_to_rgb_list(value)
        if len(color_list) > 3:
            self._white = color_list.pop()
        self._hs = color_util.color_RGB_to_hs(*color_list)


class MySensorsLightDimmer(MySensorsLight):
    """Dimmer child class to MySensorsLight."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        if self.assumed_state:
            self.async_write_ha_state()

    async def async_update(self):
        """Update the controller with the latest value from a sensor."""
        await super().async_update()
        self._async_update_light()
        self._async_update_dimmer()


class MySensorsLightRGB(MySensorsLight):
    """RGB child class to MySensorsLight."""

    @property
    def supported_features(self):
        """Flag supported features."""
        set_req = self.gateway.const.SetReq
        if set_req.V_DIMMER in self._values:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        return SUPPORT_COLOR

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w("%02x%02x%02x", **kwargs)
        if self.assumed_state:
            self.async_write_ha_state()

    async def async_update(self):
        """Update the controller with the latest value from a sensor."""
        await super().async_update()
        self._async_update_light()
        self._async_update_dimmer()
        self._async_update_rgb_or_w()


class MySensorsLightRGBW(MySensorsLightRGB):
    """RGBW child class to MySensorsLightRGB."""

    @property
    def supported_features(self):
        """Flag supported features."""
        set_req = self.gateway.const.SetReq
        if set_req.V_DIMMER in self._values:
            return SUPPORT_BRIGHTNESS | SUPPORT_MYSENSORS_RGBW
        return SUPPORT_MYSENSORS_RGBW

    async def async_turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w("%02x%02x%02x%02x", **kwargs)
        if self.assumed_state:
            self.async_write_ha_state()
