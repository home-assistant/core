"""
Support for Xiaomi Yeelight Wifi color bulb.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/yeelight/
"""
import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.discovery import SERVICE_YEELIGHT
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_SCAN_INTERVAL, \
    CONF_LIGHTS, CONF_HOST
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

REQUIREMENTS = ['yeelight==0.4.3']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "yeelight"
DATA_YEELIGHT = DOMAIN
DATA_UPDATED = '{}_data_updated'.format(DOMAIN)

DEFAULT_NAME = 'Yeelight'
DEFAULT_TRANSITION = 350

CONF_MODEL = 'model'
CONF_TRANSITION = 'transition'
CONF_SAVE_ON_CHANGE = 'save_on_change'
CONF_MODE_MUSIC = 'use_music_mode'
CONF_FLOW_PARAMS = 'flow_params'
CONF_CUSTOM_EFFECTS = 'custom_effects'

ATTR_MODE = 'mode'
ATTR_COUNT = 'count'
ATTR_ACTION = 'action'
ATTR_TRANSITIONS = 'transitions'

ACTION_RECOVER = 'recover'
ACTION_STAY = 'stay'
ACTION_OFF = 'off'

MODE_MOONLIGHT = 'moonlight'
MODE_DAYLIGHT = 'normal'

SCAN_INTERVAL = timedelta(seconds=30)

YEELIGHT_RGB_TRANSITION = 'RGBTransition'
YEELIGHT_HSV_TRANSACTION = 'HSVTransition'
YEELIGHT_TEMPERATURE_TRANSACTION = 'TemperatureTransition'
YEELIGHT_SLEEP_TRANSACTION = 'SleepTransition'

YEELIGHT_FLOW_TRANSITION_SCHEMA = {
    vol.Optional(ATTR_COUNT, default=0): cv.positive_int,
    vol.Optional(ATTR_ACTION, default=ACTION_RECOVER):
        vol.Any(ACTION_RECOVER, ACTION_OFF, ACTION_STAY),
    vol.Required(ATTR_TRANSITIONS): [{
        vol.Exclusive(YEELIGHT_RGB_TRANSITION, CONF_TRANSITION):
            vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Exclusive(YEELIGHT_HSV_TRANSACTION, CONF_TRANSITION):
            vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Exclusive(YEELIGHT_TEMPERATURE_TRANSACTION, CONF_TRANSITION):
            vol.All(cv.ensure_list, [cv.positive_int]),
        vol.Exclusive(YEELIGHT_SLEEP_TRANSACTION, CONF_TRANSITION):
            vol.All(cv.ensure_list, [cv.positive_int]),
    }]
}

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int,
    vol.Optional(CONF_MODE_MUSIC, default=False): cv.boolean,
    vol.Optional(CONF_SAVE_ON_CHANGE, default=False): cv.boolean,
    vol.Optional(CONF_MODEL): cv.string,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
        vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL):
            cv.time_period,
        vol.Optional(CONF_CUSTOM_EFFECTS): [{
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_FLOW_PARAMS): YEELIGHT_FLOW_TRANSITION_SCHEMA
        }]
    }),
}, extra=vol.ALLOW_EXTRA)

NIGHTLIGHT_SUPPORTED_MODELS = [
    "ceiling3",
    'ceiling4'
]

UPDATE_REQUEST_PROPERTIES = [
    "power",
    "bright",
    "ct",
    "rgb",
    "hue",
    "sat",
    "color_mode",
    "flowing",
    "music_on",
    "nl_br",
    "active_mode",
]


def setup(hass, config):
    """Set up the Yeelight bulbs."""
    conf = config[DOMAIN]
    hass.data[DATA_YEELIGHT] = {
        CONF_DEVICES: {},
        CONF_LIGHTS: {},
    }

    def device_discovered(service, info):
        _LOGGER.debug("Adding autodetected %s", info['hostname'])

        device_type = info['device_type']

        name = "yeelight_%s_%s" % (device_type,
                                   info['properties']['mac'])
        ipaddr = info[CONF_HOST]
        device_config = DEVICE_SCHEMA({
            CONF_NAME: name,
            CONF_MODEL: device_type
        })

        _setup_device(hass, config, ipaddr, device_config)

    discovery.listen(hass, SERVICE_YEELIGHT, device_discovered)

    def async_update(event):
        for device in hass.data[DATA_YEELIGHT][CONF_DEVICES].values():
            device.update()

    async_track_time_interval(
        hass, async_update, conf[CONF_SCAN_INTERVAL]
    )

    for ipaddr, device_config in conf[CONF_DEVICES].items():
        _LOGGER.debug("Adding configured %s", device_config[CONF_NAME])
        _setup_device(hass, config, ipaddr, device_config)

    return True


def _setup_device(hass, hass_config, ipaddr, device_config):
    devices = hass.data[DATA_YEELIGHT][CONF_DEVICES]

    if ipaddr in devices:
        return

    device = YeelightDevice(hass, ipaddr, device_config)

    devices[ipaddr] = device

    platform_config = device_config.copy()
    platform_config[CONF_HOST] = ipaddr
    platform_config[CONF_CUSTOM_EFFECTS] = \
        hass_config[DATA_YEELIGHT].get(CONF_CUSTOM_EFFECTS, {})

    load_platform(hass, LIGHT_DOMAIN, DOMAIN, platform_config, hass_config)

    if device.is_nightlight_supported:
        load_platform(hass, SWITCH_DOMAIN, DOMAIN, platform_config,
                      hass_config)


class YeelightDevice:
    """Represents single Yeelight device."""

    def __init__(self, hass, ipaddr, config):
        """Initialize device."""
        self._hass = hass
        self._config = config
        self._ipaddr = ipaddr
        self._name = config.get(CONF_NAME)
        self._model = config.get(CONF_MODEL)
        self._bulb_device = None

    @property
    def bulb(self):
        """Return bulb device."""
        import yeelight
        if self._bulb_device is None:
            try:
                self._bulb_device = yeelight.Bulb(self._ipaddr,
                                                  model=self._model)
                # force init for type
                self._update_properties()

            except yeelight.BulbException as ex:
                _LOGGER.error("Failed to connect to bulb %s, %s: %s",
                              self._ipaddr, self._name, ex)

        return self._bulb_device

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def config(self):
        """Return device config."""
        return self._config

    @property
    def ipaddr(self):
        """Return ip address."""
        return self._ipaddr

    @property
    def is_nightlight_supported(self) -> bool:
        """Return true / false if nightlight is supported."""
        return self._model in NIGHTLIGHT_SUPPORTED_MODELS

    @property
    def is_nightlight_enabled(self) -> bool:
        """Return true / false if nightlight is currently enabled."""
        return self.bulb.last_properties.get('active_mode') == '1'

    def turn_on(self, duration=DEFAULT_TRANSITION):
        """Turn on device."""
        import yeelight

        try:
            self._bulb_device.turn_on(duration=duration)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to turn the bulb on: %s", ex)
            return

        self.update()

    def turn_off(self, duration=DEFAULT_TRANSITION):
        """Turn off device."""
        import yeelight

        try:
            self._bulb_device.turn_off(duration=duration)
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to turn the bulb on: %s", ex)
            return

        self.update()

    def set_mode(self, mode: str):
        """Set a power mode."""
        import yeelight

        try:
            self.bulb.set_power_mode(yeelight.enums.PowerMode[mode.upper()])
        except yeelight.BulbException as ex:
            _LOGGER.error("Unable to set the power mode: %s", ex)

        self.update()

    def update(self):
        """Read new properties from the device."""
        if not self.bulb:
            return

        self._update_properties()
        dispatcher_send(self._hass, DATA_UPDATED, self._ipaddr)

    def _update_properties(self):
        self._bulb_device.get_properties(UPDATE_REQUEST_PROPERTIES)
