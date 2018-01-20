"""
Support for Xiaomi Philips Lights (LED Ball & Ceiling Lamp, Eyecare Lamp 2).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/light.xiaomi_miio/
"""
import asyncio
from functools import partial
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS,
    ATTR_COLOR_TEMP, SUPPORT_COLOR_TEMP, Light, ATTR_ENTITY_ID, DOMAIN, )

from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_TOKEN, )
from homeassistant.exceptions import PlatformNotReady

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Xiaomi Philips Light'
PLATFORM = 'xiaomi_miio'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(cv.string, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

REQUIREMENTS = ['python-miio==0.3.4']

# The light does not accept cct values < 1
CCT_MIN = 1
CCT_MAX = 100

SUCCESS = ['ok']
ATTR_MODEL = 'model'
ATTR_SCENE = 'scene'

SERVICE_SET_SCENE = 'xiaomi_miio_set_scene'

XIAOMI_MIIO_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})

SERVICE_SCHEMA_SCENE = XIAOMI_MIIO_SERVICE_SCHEMA.extend({
    vol.Required(ATTR_SCENE):
        vol.All(vol.Coerce(int), vol.Clamp(min=1, max=4))
})

SERVICE_TO_METHOD = {
    SERVICE_SET_SCENE: {
        'method': 'async_set_scene',
        'schema': SERVICE_SCHEMA_SCENE}
}


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the light from config."""
    from miio import Device, DeviceException
    if PLATFORM not in hass.data:
        hass.data[PLATFORM] = {}

    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    _LOGGER.info("Initializing with host %s (token %s...)", host, token[:5])

    try:
        light = Device(host, token)
        device_info = light.info()
        _LOGGER.info("%s %s %s initialized",
                     device_info.model,
                     device_info.firmware_version,
                     device_info.hardware_version)

        if device_info.model == 'philips.light.sread1':
            from miio import PhilipsEyecare
            light = PhilipsEyecare(host, token)
            device = XiaomiPhilipsEyecareLamp(name, light, device_info)
        elif device_info.model == 'philips.light.ceiling':
            from miio import Ceil
            light = Ceil(host, token)
            device = XiaomiPhilipsCeilingLamp(name, light, device_info)
        elif device_info.model == 'philips.light.bulb':
            from miio import PhilipsBulb
            light = PhilipsBulb(host, token)
            device = XiaomiPhilipsLightBall(name, light, device_info)
        else:
            _LOGGER.error(
                'Unsupported device found! Please create an issue at '
                'https://github.com/rytilahti/python-miio/issues '
                'and provide the following data: %s', device_info.model)
            return False

    except DeviceException:
        raise PlatformNotReady

    hass.data[PLATFORM][host] = device
    async_add_devices([device], update_before_add=True)

    @asyncio.coroutine
    def async_service_handler(service):
        """Map services to methods on Xiaomi Philips Lights."""
        method = SERVICE_TO_METHOD.get(service.service)
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            target_devices = [dev for dev in hass.data[PLATFORM].values()
                              if dev.entity_id in entity_ids]
        else:
            target_devices = hass.data[PLATFORM].values()

        update_tasks = []
        for target_device in target_devices:
            yield from getattr(target_device, method['method'])(**params)
            update_tasks.append(target_device.async_update_ha_state(True))

        if update_tasks:
            yield from asyncio.wait(update_tasks, loop=hass.loop)

    for xiaomi_miio_service in SERVICE_TO_METHOD:
        schema = SERVICE_TO_METHOD[xiaomi_miio_service].get(
            'schema', XIAOMI_MIIO_SERVICE_SCHEMA)
        hass.services.async_register(
            DOMAIN, xiaomi_miio_service, async_service_handler, schema=schema)


class XiaomiPhilipsGenericLight(Light):
    """Representation of a Xiaomi Philips Light."""

    def __init__(self, name, light, device_info):
        """Initialize the light device."""
        self._name = name
        self._device_info = device_info

        self._brightness = None
        self._color_temp = None

        self._light = light
        self._state = None
        self._state_attrs = {
            ATTR_MODEL: self._device_info.model,
        }

    @property
    def should_poll(self):
        """Poll the light."""
        return True

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        return self._state_attrs

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS

    @asyncio.coroutine
    def _try_command(self, mask_error, func, *args, **kwargs):
        """Call a light command handling error messages."""
        from miio import DeviceException
        try:
            result = yield from self.hass.async_add_job(
                partial(func, *args, **kwargs))

            _LOGGER.debug("Response received from light: %s", result)

            return result == SUCCESS
        except DeviceException as exc:
            _LOGGER.error(mask_error, exc)
            return False

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent_brightness = int(100 * brightness / 255)

            _LOGGER.debug(
                "Setting brightness: %s %s%%",
                self.brightness, percent_brightness)

            result = yield from self._try_command(
                "Setting brightness failed: %s",
                self._light.set_brightness, percent_brightness)

            if result:
                self._brightness = brightness

        self._state = yield from self._try_command(
            "Turning the light on failed.", self._light.on)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = yield from self._try_command(
            "Turning the light off failed.", self._light.off)

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException
        try:
            state = yield from self.hass.async_add_job(self._light.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._brightness = int(255 * 0.01 * state.brightness)

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)

    @asyncio.coroutine
    def async_set_scene(self, scene: int=1):
        """Set the fixed scene."""
        yield from self._try_command(
            "Setting a fixed scene failed.",
            self._light.set_scene, scene)

    @staticmethod
    def translate(value, left_min, left_max, right_min, right_max):
        """Map a value from left span to right span."""
        left_span = left_max - left_min
        right_span = right_max - right_min
        value_scaled = float(value - left_min) / float(left_span)
        return int(right_min + (value_scaled * right_span))


class XiaomiPhilipsLightBall(XiaomiPhilipsGenericLight, Light):
    """Representation of a Xiaomi Philips Light Ball."""

    def __init__(self, name, light, device_info):
        """Initialize the light device."""
        super().__init__(name, light, device_info)

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 175

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 333

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_COLOR_TEMP in kwargs:
            color_temp = kwargs[ATTR_COLOR_TEMP]
            percent_color_temp = self.translate(
                color_temp, self.max_mireds,
                self.min_mireds, CCT_MIN, CCT_MAX)

            _LOGGER.debug(
                "Setting color temperature: "
                "%s mireds, %s%% cct",
                color_temp, percent_color_temp)

            result = yield from self._try_command(
                "Setting color temperature failed: %s cct",
                self._light.set_color_temperature, percent_color_temp)

            if result:
                self._color_temp = color_temp

        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent_brightness = int(100 * brightness / 255)

            _LOGGER.debug(
                "Setting brightness: %s %s%%",
                self.brightness, percent_brightness)

            result = yield from self._try_command(
                "Setting brightness failed: %s",
                self._light.set_brightness, percent_brightness)

            if result:
                self._brightness = brightness

        self._state = yield from self._try_command(
            "Turning the light on failed.", self._light.on)

    @asyncio.coroutine
    def async_update(self):
        """Fetch state from the device."""
        from miio import DeviceException
        try:
            state = yield from self.hass.async_add_job(self._light.status)
            _LOGGER.debug("Got new state: %s", state)

            self._state = state.is_on
            self._brightness = int(255 * 0.01 * state.brightness)
            self._color_temp = self.translate(
                state.color_temperature,
                CCT_MIN, CCT_MAX,
                self.max_mireds, self.min_mireds)

        except DeviceException as ex:
            _LOGGER.error("Got exception while fetching the state: %s", ex)


class XiaomiPhilipsCeilingLamp(XiaomiPhilipsLightBall, Light):
    """Representation of a Xiaomi Philips Ceiling Lamp."""

    def __init__(self, name, light, device_info):
        """Initialize the light device."""
        super().__init__(name, light, device_info)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return 175

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return 370


class XiaomiPhilipsEyecareLamp(XiaomiPhilipsGenericLight, Light):
    """Representation of a Xiaomi Philips Eyecare Lamp 2."""

    def __init__(self, name, light, device_info):
        """Initialize the light device."""
        super().__init__(name, light, device_info)
