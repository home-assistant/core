"""
Support for the IKEA Tradfri platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tradfri/
"""
import asyncio
import logging

try:
    from asyncio import ensure_future
except ImportError:
    from asyncio import async as ensure_future

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR_TEMP, SUPPORT_RGB_COLOR, Light)
from homeassistant.components.light import \
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA
from homeassistant.components.tradfri import KEY_GATEWAY, KEY_TRADFRI_GROUPS, \
    KEY_API
from homeassistant.util import color as color_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['tradfri']
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA
IKEA = 'IKEA of Sweden'
TRADFRI_LIGHT_MANAGER = 'Tradfri Light Manager'
ALLOWED_TEMPERATURES = {
    IKEA: {2200: 'efd275', 2700: 'f1e0b5', 4000: 'f5faf6'}
}


@asyncio.coroutine
def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the IKEA Tradfri Light platform."""
    if discovery_info is None:
        return

    gateway_id = discovery_info['gateway']
    gateway = hass.data[KEY_GATEWAY][gateway_id]
    api = hass.data[KEY_API]

    devices_command = gateway.get_devices()
    devices_commands = yield from api(devices_command)
    devices = yield from api(*devices_commands)
    lights = [dev for dev in devices if dev.has_light_control]
    add_devices(TradfriLight(light, api, hass) for light in lights)

    allow_tradfri_groups = hass.data[KEY_TRADFRI_GROUPS][gateway_id]
    if allow_tradfri_groups:
        groups_command = gateway.get_groups()
        groups_commands = yield from api(groups_command)
        groups = yield from api(*groups_commands)
        add_devices(TradfriGroup(group, api, hass) for group in groups)


class TradfriGroup(Light):
    """The platform class required by hass."""

    def __init__(self, light, api, hass):
        """Initialize a Group."""
        self._hass = hass
        self._api = api
        self._group = light
        self._name = light.name

        self._refresh(light)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._start_observe()

    @property
    def should_poll(self):
        """No polling needed for tradfri group."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def name(self):
        """Return the display name of this group."""
        return self._name

    @property
    def is_on(self):
        """Return true if group lights are on."""
        return self._group.state

    @property
    def brightness(self):
        """Return the brightness of the group lights."""
        return self._group.dimmer

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Instruct the group lights to turn off."""
        result = yield from self._api(self._group.set_state(0))
        return result

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Instruct the group lights to turn on, or dim."""
        if ATTR_BRIGHTNESS in kwargs:
            yield from self._api(
                self._group.set_dimmer(kwargs[ATTR_BRIGHTNESS]))
        else:
            yield from self._api(self._group.set_state(1))

    def _start_observe(self, err=None):
        """Start observation of light."""
        if err:
            _LOGGER.info("Observation failed for {}".format(self._name), err)

        observe_command = self._group.observe(callback=self._observe_update,
                                              err_callback=self._start_observe,
                                              duration=0)
        observe_task = self._api(observe_command)
        ensure_future(observe_task, loop=self._hass.loop)

    def _refresh(self, group):
        """Refresh the light data."""
        self._group = group
        self._name = group.name

    def _observe_update(self, tradfri_device):
        """Receive new state data for this light."""
        self._refresh(tradfri_device)

        self.schedule_update_ha_state()


class TradfriLight(Light):
    """The platform class required by Home Asisstant."""

    def __init__(self, light, api, hass):
        """Initialize a Light."""
        self._hass = hass
        self._api = api
        self._light = None
        self._light_control = None
        self._light_data = None
        self._name = None
        self._rgb_color = None
        self._features = None
        self._ok_temps = None

        self._refresh(light)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._start_observe()

    @property
    def should_poll(self):
        """No polling needed for tradfri light."""
        return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light_data.state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._light_data.dimmer

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        if (self._light_data.hex_color is None or
                self.supported_features & SUPPORT_COLOR_TEMP == 0 or
                not self._ok_temps):
            return None

        kelvin = next((
            kelvin for kelvin, hex_color in self._ok_temps.items()
            if hex_color == self._light_data.hex_color), None)
        if kelvin is None:
            _LOGGER.error(
                "Unexpected color temperature found for %s: %s",
                self.name, self._light_data.hex_color)
            return
        return color_util.color_temperature_kelvin_to_mired(kelvin)

    @property
    def rgb_color(self):
        """RGB color of the light."""
        return self._rgb_color

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        result = yield from self._api(self._light_control.set_state(False))
        return result

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """
        Instruct the light to turn on.

        After adding "self._light_data.hexcolor is not None"
        for ATTR_RGB_COLOR, this also supports Philips Hue bulbs.
        """
        if ATTR_BRIGHTNESS in kwargs:
            yield from self._api(
                self._light_control.set_dimmer(kwargs[ATTR_BRIGHTNESS]))
        else:
            yield from self._api(self._light_control.set_state(True))

        if ATTR_RGB_COLOR in kwargs and self._light_data.hex_color is not None:
            yield from self._api(self._light.light_control.set_hex_color(
                color_util.color_rgb_to_hex(*kwargs[ATTR_RGB_COLOR])))

        elif ATTR_COLOR_TEMP in kwargs and \
                self._light_data.hex_color is not None and self._ok_temps:
            kelvin = color_util.color_temperature_mired_to_kelvin(
                kwargs[ATTR_COLOR_TEMP])
            # find closest allowed kelvin temp from user input
            kelvin = min(self._ok_temps.keys(), key=lambda x: abs(x - kelvin))
            yield from self._api(
                self._light_control.set_hex_color(self._ok_temps[kelvin]))

    def _start_observe(self, err=None):
        """Start observation of light."""
        if err:
            _LOGGER.info("Observation failed for {}".format(self._name), err)

        observe_command = self._light.observe(callback=self._observe_update,
                                              err_callback=self._start_observe,
                                              duration=0)
        observe_task = self._api(observe_command)
        ensure_future(observe_task, loop=self._hass.loop)

    def _refresh(self, light):
        """Refresh the light data."""
        self._light = light

        # Caching of LightControl and light object
        self._light_control = light.light_control
        self._light_data = light.light_control.lights[0]
        self._name = light.name
        self._rgb_color = None
        self._features = SUPPORT_BRIGHTNESS

        if self._light_data.hex_color is not None:
            if self._light.device_info.manufacturer == IKEA:
                self._features |= SUPPORT_COLOR_TEMP
            else:
                self._features |= SUPPORT_RGB_COLOR

        self._ok_temps = ALLOWED_TEMPERATURES.get(
            self._light.device_info.manufacturer)

    def _observe_update(self, tradfri_device):
        """Receive new state data for this light."""
        self._refresh(tradfri_device)

        # Handle Hue lights paired with the gateway
        # hex_color is 0 when bulb is unreachable
        if self._light_data.hex_color not in (None, '0'):
            self._rgb_color = color_util.rgb_hex_to_rgb_list(
                self._light_data.hex_color)

        self.schedule_update_ha_state()
