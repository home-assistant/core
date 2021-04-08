"""Support for IKEA Tradfri lights."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
import homeassistant.util.color as color_util

from .base_class import TradfriBaseClass, TradfriBaseDevice
from .const import (
    ATTR_DIMMER,
    ATTR_HUE,
    ATTR_SAT,
    ATTR_TRANSITION_TIME,
    CONF_GATEWAY_ID,
    CONF_IMPORT_GROUPS,
    DEVICES,
    DOMAIN,
    GROUPS,
    KEY_API,
    SUPPORTED_GROUP_FEATURES,
    SUPPORTED_LIGHT_FEATURES,
)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Tradfri lights based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    tradfri_data = hass.data[DOMAIN][config_entry.entry_id]
    api = tradfri_data[KEY_API]
    devices = tradfri_data[DEVICES]

    lights = [dev for dev in devices if dev.has_light_control]
    if lights:
        async_add_entities(TradfriLight(light, api, gateway_id) for light in lights)

    if config_entry.data[CONF_IMPORT_GROUPS]:
        groups = tradfri_data[GROUPS]
        if groups:
            async_add_entities(TradfriGroup(group, api, gateway_id) for group in groups)


class TradfriGroup(TradfriBaseClass, LightEntity):
    """The platform class for light groups required by hass."""

    def __init__(self, device, api, gateway_id):
        """Initialize a Group."""
        super().__init__(device, api, gateway_id)

        self._unique_id = f"group-{gateway_id}-{device.id}"

        self._refresh(device)

    @property
    def should_poll(self):
        """Poll needed for tradfri groups."""
        return True

    async def async_update(self):
        """Fetch new state data for the group.

        This method is required for groups to update properly.
        """
        await self._api(self._device.update())

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORTED_GROUP_FEATURES

    @property
    def is_on(self):
        """Return true if group lights are on."""
        return self._device.state

    @property
    def brightness(self):
        """Return the brightness of the group lights."""
        return self._device.dimmer

    async def async_turn_off(self, **kwargs):
        """Instruct the group lights to turn off."""
        await self._api(self._device.set_state(0))

    async def async_turn_on(self, **kwargs):
        """Instruct the group lights to turn on, or dim."""
        keys = {}
        if ATTR_TRANSITION in kwargs:
            keys["transition_time"] = int(kwargs[ATTR_TRANSITION]) * 10

        if ATTR_BRIGHTNESS in kwargs:
            if kwargs[ATTR_BRIGHTNESS] == 255:
                kwargs[ATTR_BRIGHTNESS] = 254

            await self._api(self._device.set_dimmer(kwargs[ATTR_BRIGHTNESS], **keys))
        else:
            await self._api(self._device.set_state(1))


class TradfriLight(TradfriBaseDevice, LightEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, device, api, gateway_id):
        """Initialize a Light."""
        super().__init__(device, api, gateway_id)
        self._unique_id = f"light-{gateway_id}-{device.id}"
        self._hs_color = None

        # Calculate supported features
        _features = SUPPORTED_LIGHT_FEATURES
        if device.light_control.can_set_dimmer:
            _features |= SUPPORT_BRIGHTNESS
        if device.light_control.can_set_color:
            _features |= SUPPORT_COLOR
        if device.light_control.can_set_temp:
            _features |= SUPPORT_COLOR_TEMP
        self._features = _features

        self._refresh(device)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return self._device_control.min_mireds

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return self._device_control.max_mireds

    @property
    def supported_features(self):
        """Flag supported features."""
        return self._features

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._device_data.state

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._device_data.dimmer

    @property
    def color_temp(self):
        """Return the color temp value in mireds."""
        return self._device_data.color_temp

    @property
    def hs_color(self):
        """HS color of the light."""
        if self._device_control.can_set_color:
            hsbxy = self._device_data.hsb_xy_color
            hue = hsbxy[0] / (self._device_control.max_hue / 360)
            sat = hsbxy[1] / (self._device_control.max_saturation / 100)
            if hue is not None and sat is not None:
                return hue, sat

    async def async_turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        # This allows transitioning to off, but resets the brightness
        # to 1 for the next set_state(True) command
        transition_time = None
        if ATTR_TRANSITION in kwargs:
            transition_time = int(kwargs[ATTR_TRANSITION]) * 10

            dimmer_data = {ATTR_DIMMER: 0, ATTR_TRANSITION_TIME: transition_time}
            await self._api(self._device_control.set_dimmer(**dimmer_data))
        else:
            await self._api(self._device_control.set_state(False))

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
            dimmer_data = {
                ATTR_DIMMER: brightness,
                ATTR_TRANSITION_TIME: transition_time,
            }
            dimmer_command = self._device_control.set_dimmer(**dimmer_data)
            transition_time = None
        else:
            dimmer_command = self._device_control.set_state(True)

        color_command = None
        if ATTR_HS_COLOR in kwargs and self._device_control.can_set_color:
            hue = int(kwargs[ATTR_HS_COLOR][0] * (self._device_control.max_hue / 360))
            sat = int(
                kwargs[ATTR_HS_COLOR][1] * (self._device_control.max_saturation / 100)
            )
            color_data = {
                ATTR_HUE: hue,
                ATTR_SAT: sat,
                ATTR_TRANSITION_TIME: transition_time,
            }
            color_command = self._device_control.set_hsb(**color_data)
            transition_time = None

        temp_command = None
        if ATTR_COLOR_TEMP in kwargs and (
            self._device_control.can_set_temp or self._device_control.can_set_color
        ):
            temp = kwargs[ATTR_COLOR_TEMP]
            # White Spectrum bulb
            if self._device_control.can_set_temp:
                if temp > self.max_mireds:
                    temp = self.max_mireds
                elif temp < self.min_mireds:
                    temp = self.min_mireds
                temp_data = {
                    ATTR_COLOR_TEMP: temp,
                    ATTR_TRANSITION_TIME: transition_time,
                }
                temp_command = self._device_control.set_color_temp(**temp_data)
                transition_time = None
            # Color bulb (CWS)
            # color_temp needs to be set with hue/saturation
            elif self._device_control.can_set_color:
                temp_k = color_util.color_temperature_mired_to_kelvin(temp)
                hs_color = color_util.color_temperature_to_hs(temp_k)
                hue = int(hs_color[0] * (self._device_control.max_hue / 360))
                sat = int(hs_color[1] * (self._device_control.max_saturation / 100))
                color_data = {
                    ATTR_HUE: hue,
                    ATTR_SAT: sat,
                    ATTR_TRANSITION_TIME: transition_time,
                }
                color_command = self._device_control.set_hsb(**color_data)
                transition_time = None

        # HSB can always be set, but color temp + brightness is bulb dependent
        command = dimmer_command
        if command is not None:
            command += color_command
        else:
            command = color_command

        if self._device_control.can_combine_commands:
            await self._api(command + temp_command)
        else:
            if temp_command is not None:
                await self._api(temp_command)
            if command is not None:
                await self._api(command)

    def _refresh(self, device):
        """Refresh the light data."""
        super()._refresh(device)

        # Caching of LightControl and light object
        self._device_control = device.light_control
        self._device_data = device.light_control.lights[0]
