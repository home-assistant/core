"""Support for Xiaomi Yeelight WiFi color bulb."""

from datetime import timedelta
import logging

import voluptuous as vol
from yeelight import Bulb, BulbException

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.discovery import SERVICE_YEELIGHT
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    CONF_HOST,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.discovery import load_platform
from homeassistant.helpers.dispatcher import dispatcher_connect, dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "yeelight"
DATA_YEELIGHT = DOMAIN
DATA_UPDATED = "yeelight_{}_data_updated"
DEVICE_INITIALIZED = f"{DOMAIN}_device_initialized"

DEFAULT_NAME = "Yeelight"
DEFAULT_TRANSITION = 350

CONF_MODEL = "model"
CONF_TRANSITION = "transition"
CONF_SAVE_ON_CHANGE = "save_on_change"
CONF_MODE_MUSIC = "use_music_mode"
CONF_FLOW_PARAMS = "flow_params"
CONF_CUSTOM_EFFECTS = "custom_effects"
CONF_NIGHTLIGHT_SWITCH_TYPE = "nightlight_switch_type"

ATTR_COUNT = "count"
ATTR_ACTION = "action"
ATTR_TRANSITIONS = "transitions"

ACTION_RECOVER = "recover"
ACTION_STAY = "stay"
ACTION_OFF = "off"

ACTIVE_MODE_NIGHTLIGHT = "1"
ACTIVE_COLOR_FLOWING = "1"

NIGHTLIGHT_SWITCH_TYPE_LIGHT = "light"

SCAN_INTERVAL = timedelta(seconds=30)

YEELIGHT_RGB_TRANSITION = "RGBTransition"
YEELIGHT_HSV_TRANSACTION = "HSVTransition"
YEELIGHT_TEMPERATURE_TRANSACTION = "TemperatureTransition"
YEELIGHT_SLEEP_TRANSACTION = "SleepTransition"

YEELIGHT_FLOW_TRANSITION_SCHEMA = {
    vol.Optional(ATTR_COUNT, default=0): cv.positive_int,
    vol.Optional(ATTR_ACTION, default=ACTION_RECOVER): vol.Any(
        ACTION_RECOVER, ACTION_OFF, ACTION_STAY
    ),
    vol.Required(ATTR_TRANSITIONS): [
        {
            vol.Exclusive(YEELIGHT_RGB_TRANSITION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_HSV_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_TEMPERATURE_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
            vol.Exclusive(YEELIGHT_SLEEP_TRANSACTION, CONF_TRANSITION): vol.All(
                cv.ensure_list, [cv.positive_int]
            ),
        }
    ],
}

DEVICE_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TRANSITION, default=DEFAULT_TRANSITION): cv.positive_int,
        vol.Optional(CONF_MODE_MUSIC, default=False): cv.boolean,
        vol.Optional(CONF_SAVE_ON_CHANGE, default=False): cv.boolean,
        vol.Optional(CONF_NIGHTLIGHT_SWITCH_TYPE): vol.Any(
            NIGHTLIGHT_SWITCH_TYPE_LIGHT
        ),
        vol.Optional(CONF_MODEL): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
                vol.Optional(CONF_SCAN_INTERVAL, default=SCAN_INTERVAL): cv.time_period,
                vol.Optional(CONF_CUSTOM_EFFECTS): [
                    {
                        vol.Required(CONF_NAME): cv.string,
                        vol.Required(CONF_FLOW_PARAMS): YEELIGHT_FLOW_TRANSITION_SCHEMA,
                    }
                ],
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

YEELIGHT_SERVICE_SCHEMA = vol.Schema({vol.Required(ATTR_ENTITY_ID): cv.entity_ids})

UPDATE_REQUEST_PROPERTIES = [
    "power",
    "main_power",
    "bright",
    "ct",
    "rgb",
    "hue",
    "sat",
    "color_mode",
    "flowing",
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

    def device_discovered(_, info):
        _LOGGER.debug("Adding autodetected %s", info["hostname"])

        name = "yeelight_%s_%s" % (info["device_type"], info["properties"]["mac"])

        device_config = DEVICE_SCHEMA({CONF_NAME: name})

        _setup_device(hass, config, info[CONF_HOST], device_config)

    discovery.listen(hass, SERVICE_YEELIGHT, device_discovered)

    def update(_):
        for device in list(yeelight_data.values()):
            device.update()

    track_time_interval(hass, update, conf.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL))

    def load_platforms(ipaddr):
        platform_config = hass.data[DATA_YEELIGHT][ipaddr].config.copy()
        platform_config[CONF_HOST] = ipaddr
        platform_config[CONF_CUSTOM_EFFECTS] = config.get(DOMAIN, {}).get(
            CONF_CUSTOM_EFFECTS, {}
        )
        load_platform(hass, LIGHT_DOMAIN, DOMAIN, platform_config, config)
        load_platform(hass, BINARY_SENSOR_DOMAIN, DOMAIN, platform_config, config)

    dispatcher_connect(hass, DEVICE_INITIALIZED, load_platforms)

    if DOMAIN in config:
        for ipaddr, device_config in conf[CONF_DEVICES].items():
            _LOGGER.debug("Adding configured %s", device_config[CONF_NAME])
            _setup_device(hass, config, ipaddr, device_config)

    return True


def _setup_device(hass, _, ipaddr, device_config):
    devices = hass.data[DATA_YEELIGHT]

    if ipaddr in devices:
        return

    device = YeelightDevice(hass, ipaddr, device_config)

    devices[ipaddr] = device
    hass.add_job(device.setup)


class YeelightDevice:
    """Represents single Yeelight device."""

    def __init__(self, hass, ipaddr, config):
        """Initialize device."""
        self._hass = hass
        self._config = config
        self._ipaddr = ipaddr
        self._name = config.get(CONF_NAME)
        self._model = config.get(CONF_MODEL)
        self._bulb_device = Bulb(self.ipaddr, model=self._model)
        self._device_type = None
        self._available = False
        self._initialized = False

    @property
    def bulb(self):
        """Return bulb device."""
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
    def model(self):
        """Return configured device model."""
        return self._model

    @property
    def is_nightlight_supported(self) -> bool:
        """Return true / false if nightlight is supported."""
        if self.model:
            return self.bulb.get_model_specs().get("night_light", False)

        # It should support both ceiling and other lights
        return self._nightlight_brightness is not None

    @property
    def is_nightlight_enabled(self) -> bool:
        """Return true / false if nightlight is currently enabled."""
        if self.bulb is None:
            return False

        # Only ceiling lights have active_mode, from SDK docs:
        # active_mode 0: daylight mode / 1: moonlight mode (ceiling light only)
        if self._active_mode is not None:
            return self._active_mode == ACTIVE_MODE_NIGHTLIGHT

        if self._nightlight_brightness is not None:
            return int(self._nightlight_brightness) > 0

        return False

    @property
    def is_color_flow_enabled(self) -> bool:
        """Return true / false if color flow is currently running."""
        return self._color_flow == ACTIVE_COLOR_FLOWING

    @property
    def _active_mode(self):
        return self.bulb.last_properties.get("active_mode")

    @property
    def _color_flow(self):
        return self.bulb.last_properties.get("flowing")

    @property
    def _nightlight_brightness(self):
        return self.bulb.last_properties.get("nl_br")

    @property
    def type(self):
        """Return bulb type."""
        if not self._device_type:
            self._device_type = self.bulb.bulb_type

        return self._device_type

    def turn_on(self, duration=DEFAULT_TRANSITION, light_type=None, power_mode=None):
        """Turn on device."""
        try:
            self.bulb.turn_on(
                duration=duration, light_type=light_type, power_mode=power_mode
            )
        except BulbException as ex:
            _LOGGER.error("Unable to turn the bulb on: %s", ex)

    def turn_off(self, duration=DEFAULT_TRANSITION, light_type=None):
        """Turn off device."""
        try:
            self.bulb.turn_off(duration=duration, light_type=light_type)
        except BulbException as ex:
            _LOGGER.error(
                "Unable to turn the bulb off: %s, %s: %s", self.ipaddr, self.name, ex
            )

    def _update_properties(self):
        """Read new properties from the device."""
        if not self.bulb:
            return

        try:
            self.bulb.get_properties(UPDATE_REQUEST_PROPERTIES)
            self._available = True
            if not self._initialized:
                self._initialize_device()
        except BulbException as ex:
            if self._available:  # just inform once
                _LOGGER.error(
                    "Unable to update device %s, %s: %s", self.ipaddr, self.name, ex
                )
            self._available = False

        return self._available

    def _initialize_device(self):
        self._initialized = True
        dispatcher_send(self._hass, DEVICE_INITIALIZED, self.ipaddr)

    def update(self):
        """Update device properties and send data updated signal."""
        self._update_properties()
        dispatcher_send(self._hass, DATA_UPDATED.format(self._ipaddr))

    def setup(self):
        """Fetch initial device properties."""
        initial_update = self._update_properties()

        # We can build correct class anyway.
        if not initial_update and self.model:
            self._initialize_device()
