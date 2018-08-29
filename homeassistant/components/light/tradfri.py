"""
Support for the IKEA Tradfri platform.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tradfri/
"""
import logging

from homeassistant.core import callback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_HS_COLOR, ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS, SUPPORT_TRANSITION, SUPPORT_COLOR_TEMP,
    SUPPORT_COLOR, Light)
from homeassistant.components.light import \
    PLATFORM_SCHEMA as LIGHT_PLATFORM_SCHEMA
from homeassistant.components.tradfri import KEY_GATEWAY, KEY_TRADFRI_GROUPS, \
    KEY_API
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

ATTR_DIMMER = 'dimmer'
ATTR_HUE = 'hue'
ATTR_SAT = 'saturation'
ATTR_TRANSITION_TIME = 'transition_time'
DEPENDENCIES = ['tradfri']
PLATFORM_SCHEMA = LIGHT_PLATFORM_SCHEMA
IKEA = 'IKEA of Sweden'
TRADFRI_LIGHT_MANAGER = 'Tradfri Light Manager'
SUPPORTED_FEATURES = SUPPORT_TRANSITION
SUPPORTED_GROUP_FEATURES = SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION


async def async_setup_platform(hass, config,
                               async_add_entities, discovery_info=None):
    """Set up the IKEA Tradfri Light platform."""
    if discovery_info is None:
        return

    gateway_id = discovery_info['gateway']
    api = hass.data[KEY_API][gateway_id]
    gateway = hass.data[KEY_GATEWAY][gateway_id]

    devices_command = gateway.get_devices()
    devices_commands = await api(devices_command)
    devices = await api(devices_commands)
    lights = [dev for dev in devices if dev.has_light_control]
    if lights:
        async_add_entities(
            TradfriLight(light, api, gateway_id) for light in lights)

    allow_tradfri_groups = hass.data[KEY_TRADFRI_GROUPS][gateway_id]
    if allow_tradfri_groups:
        groups_command = gateway.get_groups()
        groups_commands = await api(groups_command)
        groups = await api(groups_commands)
        if groups:
            async_add_entities(
                TradfriGroup(group, api, gateway_id) for group in groups)


class TradfriGroup(Light):
    """The platform class required by hass."""

    def __init__(self, group, api, gateway_id):
        """Initialize a Group."""
        self._api = api
        self._unique_id = "group-{}-{}".format(gateway_id, group.id)
        self._group = group
        self._name = group.name

        self._refresh(group)

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def unique_id(self):
        """Return unique ID for this group."""
        return self._unique_id

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_GROUP_FEATURES

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

    async def async_turn_off(self, **kwargs):
        """Instruct the group lights to turn off."""
        await self._api(self._group.set_state(0))

    async def async_turn_on(self, **kwargs):
        """Instruct the group lights to turn on, or dim."""
        keys = {}
        if ATTR_TRANSITION in kwargs:
            keys['transition_time'] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_BRIGHTNESS in kwargs:
            if kwargs[ATTR_BRIGHTNESS] == 255:
                kwargs[ATTR_BRIGHTNESS] = 254

            await self._api(
                self._group.set_dimmer(kwargs[ATTR_BRIGHTNESS], **keys))
        else:
            await self._api(self._group.set_state(1))

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of light."""
        # pylint: disable=import-error
        from pytradfri.error import PytradfriError
        if exc:
            _LOGGER.warning("Observation failed for %s", self._name,
                            exc_info=exc)

        try:
            cmd = self._group.observe(callback=self._observe_update,
                                      err_callback=self._async_start_observe,
                                      duration=0)
            self.hass.async_add_job(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, group):
        """Refresh the light data."""
        self._group = group
        self._name = group.name

    @callback
    def _observe_update(self, tradfri_device):
        """Receive new state data for this light."""
        self._refresh(tradfri_device)
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """Fetch new state data for the group."""
        await self._api(self._group.update())


class TradfriLight(Light):
    """The platform class required by Home Assistant."""

    def __init__(self, light, api, gateway_id):
        """Initialize a Light."""
        self._api = api
        self._unique_id = "light-{}-{}".format(gateway_id, light.id)
        self._light = None
        self._light_control = None
        self._light_data = None
        self._name = None
        self._hs_color = None
        self._features = SUPPORTED_FEATURES
        self._available = True

        self._refresh(light)

    @property
    def unique_id(self):
        """Return unique ID for light."""
        return self._unique_id

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._light_control.min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._light_control.max_mireds

    async def async_added_to_hass(self):
        """Start thread when added to hass."""
        self._async_start_observe()

    @property
    def available(self):
        """Return True if entity is available."""
        return self._available

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
        """Return the color temp value in mireds."""
        return self._light_data.color_temp

    @property
    def hs_color(self):
        """HS color of the light."""
        if self._light_control.can_set_color:
            hsbxy = self._light_data.hsb_xy_color
            hue = hsbxy[0] / (self._light_control.max_hue / 360)
            sat = hsbxy[1] / (self._light_control.max_saturation / 100)
            if hue is not None and sat is not None:
                return hue, sat

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        # This allows transitioning to off, but resets the brightness
        # to 1 for the next set_state(True) command
        transition_time = None
        if ATTR_TRANSITION in kwargs:
            transition_time = int(kwargs[ATTR_TRANSITION]) * 10

            dimmer_data = {ATTR_DIMMER: 0, ATTR_TRANSITION_TIME:
                           transition_time}
            await self._api(self._light_control.set_dimmer(**dimmer_data))
        else:
            await self._api(self._light_control.set_state(False))

    async def async_turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        transition_time = None
        if ATTR_TRANSITION in kwargs:
            transition_time = int(kwargs[ATTR_TRANSITION]) * 10

        dimmer_command = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            if brightness > 254:
                brightness = 254
            elif brightness < 0:
                brightness = 0
            dimmer_data = {ATTR_DIMMER: brightness, ATTR_TRANSITION_TIME:
                           transition_time}
            dimmer_command = self._light_control.set_dimmer(**dimmer_data)
            transition_time = None
        else:
            dimmer_command = self._light_control.set_state(True)

        color_command = None
        if ATTR_HS_COLOR in kwargs and self._light_control.can_set_color:
            hue = int(kwargs[ATTR_HS_COLOR][0] *
                      (self._light_control.max_hue / 360))
            sat = int(kwargs[ATTR_HS_COLOR][1] *
                      (self._light_control.max_saturation / 100))
            color_data = {ATTR_HUE: hue, ATTR_SAT: sat, ATTR_TRANSITION_TIME:
                          transition_time}
            color_command = self._light_control.set_hsb(**color_data)
            transition_time = None

        temp_command = None
        if ATTR_COLOR_TEMP in kwargs and (self._light_control.can_set_temp or
                                          self._light_control.can_set_color):
            temp = kwargs[ATTR_COLOR_TEMP]
            # White Spectrum bulb
            if self._light_control.can_set_temp:
                if temp > self.max_mireds:
                    temp = self.max_mireds
                elif temp < self.min_mireds:
                    temp = self.min_mireds
                temp_data = {ATTR_COLOR_TEMP: temp, ATTR_TRANSITION_TIME:
                             transition_time}
                temp_command = self._light_control.set_color_temp(**temp_data)
                transition_time = None
            # Color bulb (CWS)
            # color_temp needs to be set with hue/saturation
            elif self._light_control.can_set_color:
                temp_k = color_util.color_temperature_mired_to_kelvin(temp)
                hs_color = color_util.color_temperature_to_hs(temp_k)
                hue = int(hs_color[0] * (self._light_control.max_hue / 360))
                sat = int(hs_color[1] *
                          (self._light_control.max_saturation / 100))
                color_data = {ATTR_HUE: hue, ATTR_SAT: sat,
                              ATTR_TRANSITION_TIME: transition_time}
                color_command = self._light_control.set_hsb(**color_data)
                transition_time = None

        # HSB can always be set, but color temp + brightness is bulb dependant
        command = dimmer_command
        if command is not None:
            command += color_command
        else:
            command = color_command

        if self._light_control.can_combine_commands:
            await self._api(command + temp_command)
        else:
            if temp_command is not None:
                await self._api(temp_command)
            if command is not None:
                await self._api(command)

    @callback
    def _async_start_observe(self, exc=None):
        """Start observation of light."""
        # pylint: disable=import-error
        from pytradfri.error import PytradfriError
        if exc:
            _LOGGER.warning("Observation failed for %s", self._name,
                            exc_info=exc)

        try:
            cmd = self._light.observe(callback=self._observe_update,
                                      err_callback=self._async_start_observe,
                                      duration=0)
            self.hass.async_add_job(self._api(cmd))
        except PytradfriError as err:
            _LOGGER.warning("Observation failed, trying again", exc_info=err)
            self._async_start_observe()

    def _refresh(self, light):
        """Refresh the light data."""
        self._light = light

        # Caching of LightControl and light object
        self._available = light.reachable
        self._light_control = light.light_control
        self._light_data = light.light_control.lights[0]
        self._name = light.name
        self._features = SUPPORTED_FEATURES

        if light.light_control.can_set_dimmer:
            self._features |= SUPPORT_BRIGHTNESS
        if light.light_control.can_set_color:
            self._features |= SUPPORT_COLOR
        if light.light_control.can_set_temp:
            self._features |= SUPPORT_COLOR_TEMP

    @callback
    def _observe_update(self, tradfri_device):
        """Receive new state data for this light."""
        self._refresh(tradfri_device)
        self.async_schedule_update_ha_state()
