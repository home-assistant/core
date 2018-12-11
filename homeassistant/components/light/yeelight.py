"""
Support for Xiaomi Yeelight Wifi color bulb.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.yeelight/
"""
import logging

import voluptuous as vol

from homeassistant.util.color import (
    color_temperature_mired_to_kelvin as mired_to_kelvin,
    color_temperature_kelvin_to_mired as kelvin_to_mired)
from homeassistant.const import CONF_DEVICES, CONF_NAME
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ATTR_TRANSITION, ATTR_COLOR_TEMP,
    ATTR_FLASH, FLASH_SHORT, FLASH_LONG, ATTR_EFFECT, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, SUPPORT_TRANSITION, SUPPORT_COLOR_TEMP, SUPPORT_FLASH,
    SUPPORT_EFFECT, Light, PLATFORM_SCHEMA, ATTR_ENTITY_ID, DOMAIN)
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

REQUIREMENTS = ['yeelight==0.4.3']

_LOGGER = logging.getLogger(__name__)

LEGACY_DEVICE_TYPE_MAP = {
    'color1': 'rgb',
    'mono1': 'white',
    'strip1': 'strip',
    'bslamp1': 'bedside',
    'ceiling1': 'ceiling',
}

DEFAULT_NAME = 'Yeelight'
DEFAULT_TRANSITION = 350

CONF_MODEL = 'model'
CONF_TRANSITION = 'transition'
CONF_SAVE_ON_CHANGE = 'save_on_change'
CONF_MODE_MUSIC = 'use_music_mode'

DATA_KEY = 'light.yeelight'

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int,
    vol.Optional(CONF_MODE_MUSIC, default=False): cv.boolean,
    vol.Optional(CONF_SAVE_ON_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_MODEL): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA}, })

SUPPORT_YEELIGHT = (SUPPORT_BRIGHTNESS |
                    SUPPORT_TRANSITION |
                    SUPPORT_FLASH)

SUPPORT_YEELIGHT_WHITE_TEMP = (SUPPORT_YEELIGHT |
                               SUPPORT_COLOR_TEMP)

SUPPORT_YEELIGHT_RGB = (SUPPORT_YEELIGHT |
                        SUPPORT_COLOR |
                        SUPPORT_EFFECT |
                        SUPPORT_COLOR_TEMP)

EFFECT_DISCO = "Disco"
EFFECT_TEMP = "Slow Temp"
EFFECT_STROBE = "Strobe epilepsy!"
EFFECT_STROBE_COLOR = "Strobe color"
EFFECT_ALARM = "Alarm"
EFFECT_POLICE = "Police"
EFFECT_POLICE2 = "Police2"
EFFECT_CHRISTMAS = "Christmas"
EFFECT_RGB = "RGB"
EFFECT_RANDOM_LOOP = "Random Loop"
EFFECT_FAST_RANDOM_LOOP = "Fast Random Loop"
EFFECT_LSD = "LSD"
EFFECT_SLOWDOWN = "Slowdown"
EFFECT_WHATSAPP = "WhatsApp"
EFFECT_FACEBOOK = "Facebook"
EFFECT_TWITTER = "Twitter"
EFFECT_STOP = "Stop"

YEELIGHT_EFFECT_LIST = [
    EFFECT_DISCO,
    EFFECT_TEMP,
    EFFECT_STROBE,
    EFFECT_STROBE_COLOR,
    EFFECT_ALARM,
    EFFECT_POLICE,
    EFFECT_POLICE2,
    EFFECT_CHRISTMAS,
    EFFECT_RGB,
    EFFECT_RANDOM_LOOP,
    EFFECT_FAST_RANDOM_LOOP,
    EFFECT_LSD,
    EFFECT_SLOWDOWN,
    EFFECT_WHATSAPP,
    EFFECT_FACEBOOK,
    EFFECT_TWITTER,
    EFFECT_STOP]

SERVICE_SET_MODE = 'yeelight_set_mode'
ATTR_MODE = 'mode'

YEELIGHT_SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
})


def _cmd(func):
    """Define a wrapper to catch exceptions from the bulb."""
    def _wrap(self, *args, **kwargs):
        import yeelight
        try:
            _LOGGER.debug("Calling %s with %s %s", func, args, kwargs)
            return func(self, *args, **kwargs)
        except yeelight.BulbException as ex:
            _LOGGER.error("Error when calling %s: %s", func, ex)

    return _wrap


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Yeelight bulbs."""
    from yeelight.enums import PowerMode

    if DATA_KEY not in hass.data:
        hass.data[DATA_KEY] = {}

    lights = []
    if discovery_info is not None:
        _LOGGER.debug("Adding autodetected %s", discovery_info['hostname'])

        device_type = discovery_info['device_type']
        legacy_device_type = LEGACY_DEVICE_TYPE_MAP.get(device_type,
                                                        device_type)

        # Not using hostname, as it seems to vary.
        name = "yeelight_%s_%s" % (legacy_device_type,
                                   discovery_info['properties']['mac'])
        device = {'name': name, 'ipaddr': discovery_info['host']}

        light = YeelightLight(device, DEVICE_SCHEMA({CONF_MODEL: device_type}))
        lights.append(light)
        hass.data[DATA_KEY][name] = light
    else:
        for ipaddr, device_config in config[CONF_DEVICES].items():
            name = device_config[CONF_NAME]
            _LOGGER.debug("Adding configured %s", name)

            device = {'name': name, 'ipaddr': ipaddr}
            light = YeelightLight(device, device_config)
            lights.append(light)
            hass.data[DATA_KEY][name] = light

    add_entities(lights, True)

    def service_handler(service):
        """Dispatch service calls to target entities."""
        params = {key: value for key, value in service.data.items()
                  if key != ATTR_ENTITY_ID}
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        if entity_ids:
            target_devices = [dev for dev in hass.data[DATA_KEY].values()
                              if dev.entity_id in entity_ids]
        else:
            target_devices = hass.data[DATA_KEY].values()

        for target_device in target_devices:
            if service.service == SERVICE_SET_MODE:
                target_device.set_mode(**params)

    service_schema_set_mode = YEELIGHT_SERVICE_SCHEMA.extend({
        vol.Required(ATTR_MODE):
            vol.In([mode.name.lower() for mode in PowerMode])
    })
    hass.services.register(
        DOMAIN, SERVICE_SET_MODE, service_handler,
        schema=service_schema_set_mode)


class YeelightLight(Light):
    """Representation of a Yeelight light."""

    def __init__(self, device, config):
        """Initialize the Yeelight light."""
        self.config = config
        self._name = device['name']
        self._ipaddr = device['ipaddr']

        self._supported_features = SUPPORT_YEELIGHT
        self._available = False
        self._bulb_device = None

        self._brightness = None
        self._color_temp = None
        self._is_on = None
        self._hs = None

        self._model = config.get('model')
        self._min_mireds = None
        self._max_mireds = None

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._available

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._supported_features

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return YEELIGHT_EFFECT_LIST

    @property
    def color_temp(self) -> int:
        """Return the color temperature."""
        return self._color_temp

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._is_on

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 1..255."""
        return self._brightness

    @property
    def min_mireds(self):
        """Return minimum supported color temperature."""
        return self._min_mireds

    @property
    def max_mireds(self):
        """Return maximum supported color temperature."""
        return self._max_mireds

    def _get_hs_from_properties(self):
        rgb = self._properties.get('rgb', None)
        color_mode = self._properties.get('color_mode', None)
        if not rgb or not color_mode:
            return None

        color_mode = int(color_mode)
        if color_mode == 2:  # color temperature
            temp_in_k = mired_to_kelvin(self._color_temp)
            return color_util.color_temperature_to_hs(temp_in_k)
        if color_mode == 3:  # hsv
            hue = int(self._properties.get('hue'))
            sat = int(self._properties.get('sat'))
            return (hue / 360 * 65536, sat / 100 * 255)

        rgb = int(rgb)
        blue = rgb & 0xff
        green = (rgb >> 8) & 0xff
        red = (rgb >> 16) & 0xff

        return color_util.color_RGB_to_hs(red, green, blue)

    @property
    def hs_color(self) -> tuple:
        """Return the color property."""
        return self._hs

    @property
    def _properties(self) -> dict:
        if self._bulb_device is None:
            return {}
        return self._bulb_device.last_properties

    # F821: https://github.com/PyCQA/pyflakes/issues/373
    @property
    def _bulb(self) -> 'yeelight.Bulb':  # noqa: F821
        import yeelight
        if self._bulb_device is None:
            try:
                self._bulb_device = yeelight.Bulb(self._ipaddr,
                                                  model=self._model)
                self._bulb_device.get_properties()  # force init for type

                self._available = True
            except yeelight.BulbException as ex:
                self._available = False
                _LOGGER.error("Failed to connect to bulb %s, %s: %s",
                              self._ipaddr, self._name, ex)

        return self._bulb_device

    def set_music_mode(self, mode) -> None:
        """Set the music mode on or off."""
        if mode:
            self._bulb.start_music()
        else:
            self._bulb.stop_music()

    def update(self) -> None:
        """Update properties from the bulb."""
        import yeelight
        try:
            self._bulb.get_properties()

            if self._bulb_device.bulb_type == yeelight.BulbType.Color:
                self._supported_features = SUPPORT_YEELIGHT_RGB
            elif self._bulb_device.bulb_type == yeelight.BulbType.WhiteTemp:
                self._supported_features = SUPPORT_YEELIGHT_WHITE_TEMP

            if self._min_mireds is None:
                model_specs = self._bulb.get_model_specs()
                self._min_mireds = \
                    kelvin_to_mired(model_specs['color_temp']['max'])
                self._max_mireds = \
                    kelvin_to_mired(model_specs['color_temp']['min'])

            self._is_on = self._properties.get('power') == 'on'

            bright = self._properties.get('bright', None)
            if bright:
                self._brightness = round(255 * (int(bright) / 100))

            temp_in_k = self._properties.get('ct', None)
            if temp_in_k:
                self._color_temp = kelvin_to_mired(int(temp_in_k))

            self._hs = self._get_hs_from_properties()

            self._available = True
        except yeelight.BulbException as ex:
            if self._available:  # just inform once
                _LOGGER.error("Unable to update bulb status: %s", ex)
            self._available = False

    @_cmd
    def set_brightness(self, brightness, duration) -> None:
        """Set bulb brightness."""
        if brightness:
            _LOGGER.debug("Setting brightness: %s", brightness)
            self._bulb.set_brightness(brightness / 255 * 100,
                                      duration=duration)

    @_cmd
    def set_rgb(self, rgb, duration) -> None:
        """Set bulb's color."""
        if rgb and self.supported_features & SUPPORT_COLOR:
            _LOGGER.debug("Setting RGB: %s", rgb)
            self._bulb.set_rgb(rgb[0], rgb[1], rgb[2], duration=duration)

    @_cmd
    def set_colortemp(self, colortemp, duration) -> None:
        """Set bulb's color temperature."""
        if colortemp and self.supported_features & SUPPORT_COLOR_TEMP:
            temp_in_k = mired_to_kelvin(colortemp)
            _LOGGER.debug("Setting color temp: %s K", temp_in_k)

            self._bulb.set_color_temp(temp_in_k, duration=duration)

    @_cmd
    def set_default(self) -> None:
        """Set current options as default."""
        self._bulb.set_default()

    @_cmd
    def set_flash(self, flash) -> None:
        """Activate flash."""
        if flash:
            from yeelight import (RGBTransition, SleepTransition, Flow,
                                  BulbException)
            if self._bulb.last_properties["color_mode"] != 1:
                _LOGGER.error("Flash supported currently only in RGB mode.")
                return

            transition = int(self.config[CONF_TRANSITION])
            if flash == FLASH_LONG:
                count = 1
                duration = transition * 5
            if flash == FLASH_SHORT:
                count = 1
                duration = transition * 2

            red, green, blue = color_util.color_hs_to_RGB(*self._hs)

            transitions = list()
            transitions.append(
                RGBTransition(255, 0, 0, brightness=10, duration=duration))
            transitions.append(SleepTransition(
                duration=transition))
            transitions.append(
                RGBTransition(red, green, blue, brightness=self.brightness,
                              duration=duration))

            flow = Flow(count=count, transitions=transitions)
            try:
                self._bulb.start_flow(flow)
            except BulbException as ex:
                _LOGGER.error("Unable to set flash: %s", ex)

    @_cmd
    def set_effect(self, effect) -> None:
        """Activate effect."""
        if effect:
            from yeelight import (Flow, BulbException)
            from yeelight.transitions import (disco, temp, strobe, pulse,
                                              strobe_color, alarm, police,
                                              police2, christmas, rgb,
                                              randomloop, lsd, slowdown)
            if effect == EFFECT_STOP:
                self._bulb.stop_flow()
                return

            effects_map = {
                EFFECT_DISCO: disco,
                EFFECT_TEMP: temp,
                EFFECT_STROBE: strobe,
                EFFECT_STROBE_COLOR: strobe_color,
                EFFECT_ALARM: alarm,
                EFFECT_POLICE: police,
                EFFECT_POLICE2: police2,
                EFFECT_CHRISTMAS: christmas,
                EFFECT_RGB: rgb,
                EFFECT_RANDOM_LOOP: randomloop,
                EFFECT_LSD: lsd,
                EFFECT_SLOWDOWN: slowdown,
            }

            if effect in effects_map:
                flow = Flow(count=0, transitions=effects_map[effect]())
            if effect == EFFECT_FAST_RANDOM_LOOP:
                flow = Flow(count=0, transitions=randomloop(duration=250))
            if effect == EFFECT_WHATSAPP:
                flow = Flow(count=2, transitions=pulse(37, 211, 102))
            if effect == EFFECT_FACEBOOK:
                flow = Flow(count=2, transitions=pulse(59, 89, 152))
            if effect == EFFECT_TWITTER:
                flow = Flow(count=2, transitions=pulse(0, 172, 237))

            try:
                self._bulb.start_flow(flow)
            except BulbException as ex:
                _LOGGER.error("Unable to set effect: %s", ex)

    def turn_on(self, **kwargs) -> None:
        """Turn the bulb on."""
        import yeelight
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp = kwargs.get(ATTR_COLOR_TEMP)
        hs_color = kwargs.get(ATTR_HS_COLOR)
        rgb = color_util.color_hs_to_RGB(*hs_color) if hs_color else None
        flash = kwargs.get(ATTR_FLASH)
        effect = kwargs.get(ATTR_EFFECT)

        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s

        try:
            self._bulb.turn_on(duration=duration)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to turn the bulb on: %s", ex)
            return

        if self.config[CONF_MODE_MUSIC] and not self._bulb.music_mode:
            try:
                self.set_music_mode(self.config[CONF_MODE_MUSIC])
            except yeelight.BulbException as ex:
                _LOGGER.error("Unable to turn on music mode,"
                              "consider disabling it: %s", ex)

        try:
            # values checked for none in methods
            self.set_rgb(rgb, duration)
            self.set_colortemp(colortemp, duration)
            self.set_brightness(brightness, duration)
            self.set_flash(flash)
            self.set_effect(effect)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to set bulb properties: %s", ex)
            return

        # save the current state if we had a manual change.
        if self.config[CONF_SAVE_ON_CHANGE] and (brightness
                                                 or colortemp
                                                 or rgb):
            try:
                self.set_default()
            except yeelight.BulbException as ex:
                _LOGGER.error("Unable to set the defaults: %s", ex)
                return

    def turn_off(self, **kwargs) -> None:
        """Turn off."""
        import yeelight
        duration = int(self.config[CONF_TRANSITION])  # in ms
        if ATTR_TRANSITION in kwargs:  # passed kwarg overrides config
            duration = int(kwargs.get(ATTR_TRANSITION) * 1000)  # kwarg in s
        try:
            self._bulb.turn_off(duration=duration)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to turn the bulb off: %s", ex)

    def set_mode(self, mode: str):
        """Set a power mode."""
        import yeelight
        try:
            self._bulb.set_power_mode(yeelight.enums.PowerMode[mode.upper()])
            self.async_schedule_update_ha_state(True)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to set the power mode: %s", ex)
