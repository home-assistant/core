"""Support for Xiaomi Yeelight WiFi color bulb."""

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.discovery import SERVICE_YEELIGHT
from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_SCAN_INTERVAL, \
    CONF_HOST, ATTR_ENTITY_ID
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.binary_sensor import DOMAIN as \
    BINARY_SENSOR_DOMAIN
from homeassistant.helpers import discovery
from homeassistant.helpers.discovery import load_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "yeelight"
DATA_YEELIGHT = DOMAIN
DATA_UPDATED = 'yeelight_{}_data_updated'

DEFAULT_NAME = 'Yeelight'
DEFAULT_TRANSITION = 350

CONF_MODEL = 'model'
CONF_TRANSITION = 'transition'
CONF_SAVE_ON_CHANGE = 'save_on_change'
CONF_MODE_MUSIC = 'use_music_mode'
CONF_FLOW_PARAMS = 'flow_params'
CONF_CUSTOM_EFFECTS = 'custom_effects'

ATTR_COUNT = 'count'
ATTR_ACTION = 'action'
ATTR_TRANSITIONS = 'transitions'

ACTION_RECOVER = 'recover'
ACTION_STAY = 'stay'
ACTION_OFF = 'off'

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

YEELIGHT_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_ENTITY_ID): cv.entity_ids,
})

UPDATE_REQUEST_PROPERTIES = [
    "power",
    "main_power",
    "bright",
    "ct",
    "rgb",
    "hue",
    "sat",
    "color_mode",
    "bg_power",
    "bg_lmode",
    "bg_flowing",
    "bg_ct",
    "bg_bright",
    "bg_hue",
    "bg_sat",
    "bg_rgb",
    "nl_br",
    "active_mode",
]


def setup(hass, config):
    """Set up the Yeelight bulbs."""
    conf = config.get(DOMAIN, {})
    yeelight_data = hass.data[DATA_YEELIGHT] = {}

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

    def update(event):
        for device in list(yeelight_data.values()):
            device.update()

    track_time_interval(
        hass, update, conf.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    )

    if DOMAIN in config:
        for ipaddr, device_config in conf[CONF_DEVICES].items():
            _LOGGER.debug("Adding configured %s", device_config[CONF_NAME])
            _setup_device(hass, config, ipaddr, device_config)

    return True


def _setup_device(hass, hass_config, ipaddr, device_config):
    devices = hass.data[DATA_YEELIGHT]

    if ipaddr in devices:
        return

    device = YeelightDevice(hass, ipaddr, device_config)

    devices[ipaddr] = device

    platform_config = device_config.copy()
    platform_config[CONF_HOST] = ipaddr
    platform_config[CONF_CUSTOM_EFFECTS] = \
        hass_config.get(DOMAIN, {}).get(CONF_CUSTOM_EFFECTS, {})

    load_platform(hass, LIGHT_DOMAIN, DOMAIN, platform_config, hass_config)
    load_platform(hass, BINARY_SENSOR_DOMAIN, DOMAIN, platform_config,
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
        self._available = False

    @property
    def bulb(self):
        """Return bulb device."""
        if self._bulb_device is None:
            from yeelight import Bulb, BulbException
            try:
                self._bulb_device = Bulb(self._ipaddr, model=self._model)
                # force init for type
                self.update()

                self._available = True
            except BulbException as ex:
                self._available = False
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
    def available(self):
        """Return true is device is available."""
        return self._available

    @property
    def is_nightlight_enabled(self) -> bool:
        """Return true / false if nightlight is currently enabled."""
        if self.bulb is None:
            return False

        return self.bulb.last_properties.get('active_mode') == '1'

    @property
    def is_nightlight_supported(self) -> bool:
        """Return true / false if nightlight is supported."""
        return self.bulb.get_model_specs().get('night_light', False)

    @property
    def is_ambilight_supported(self) -> bool:
        """Return true / false if ambilight is supported."""
        return self.bulb.get_model_specs().get('background_light', False)

    def turn_on(self, duration=DEFAULT_TRANSITION, light_type=None):
        """Turn on device."""
        from yeelight import BulbException

        try:
            self.bulb.turn_on(duration=duration, light_type=light_type)
        except BulbException as ex:
            _LOGGER.error("Unable to turn the bulb on: %s", ex)
            return

    def turn_off(self, duration=DEFAULT_TRANSITION, light_type=None):
        """Turn off device."""
        from yeelight import BulbException

        try:
            self.bulb.turn_off(duration=duration, light_type=light_type)
        except BulbException as ex:
            _LOGGER.error("Unable to turn the bulb off: %s", ex)
            return

    def update(self):
        """Read new properties from the device."""
        from yeelight import BulbException

        if not self.bulb:
            return

        try:
            self.bulb.get_properties(UPDATE_REQUEST_PROPERTIES)
            self._available = True
        except BulbException as ex:
            if self._available:  # just inform once
                _LOGGER.error("Unable to update bulb status: %s", ex)
            self._available = False

        dispatcher_send(self._hass, DATA_UPDATED.format(self._ipaddr))
