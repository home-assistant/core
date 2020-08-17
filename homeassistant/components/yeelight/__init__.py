"""Support for Xiaomi Yeelight WiFi color bulb."""
import asyncio
from datetime import timedelta
import logging
from typing import Optional

import voluptuous as vol
from yeelight import Bulb, BulbException, discover_bulbs

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICES,
    CONF_DISCOVERY,
    CONF_IP_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "yeelight"
DATA_YEELIGHT = DOMAIN
DATA_UPDATED = "yeelight_{}_data_updated"
DEVICE_INITIALIZED = f"{DOMAIN}_device_initialized"

DEFAULT_NAME = "Yeelight"
DEFAULT_TRANSITION = 350
DEFAULT_MODE_MUSIC = False
DEFAULT_SAVE_ON_CHANGE = False
DEFAULT_NIGHTLIGHT_SWITCH = False

CONF_MODEL = "model"
CONF_TRANSITION = "transition"
CONF_SAVE_ON_CHANGE = "save_on_change"
CONF_MODE_MUSIC = "use_music_mode"
CONF_FLOW_PARAMS = "flow_params"
CONF_CUSTOM_EFFECTS = "custom_effects"
CONF_NIGHTLIGHT_SWITCH_TYPE = "nightlight_switch_type"
CONF_NIGHTLIGHT_SWITCH = "nightlight_switch"
CONF_DEVICE = "device"

DATA_CONFIG_ENTRIES = "config_entries"
DATA_CUSTOM_EFFECTS = "custom_effects"
DATA_DEVICES = "devices"
DATA_SCANNER = "scanner"
DATA_UNSUB_UPDATE_LISTENER = "unsub_update_listener"
DATA_SETUP_BINARY_SENSOR = "setup_binary_sensor"
DATA_SETUP_LIGHT = "setup_light"

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
DISCOVERY_INTERVAL = timedelta(seconds=60)

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

PLATFORMS = ["binary_sensor", "light"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Yeelight bulbs."""
    conf = config.get(DOMAIN, {})
    yeelight_data = hass.data[DOMAIN] = {
        DATA_CUSTOM_EFFECTS: conf.get(CONF_CUSTOM_EFFECTS, {}),
        DATA_CONFIG_ENTRIES: {},
        DATA_DEVICES: {},
    }

    async def async_update(_):
        await asyncio.gather(
            *[
                hass.async_add_executor_job(device.update)
                for device in list(yeelight_data[DATA_DEVICES].values())
            ]
        )

    async_track_time_interval(
        hass, async_update, conf.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    )

    # Import manually configured devices
    for ipaddr, device_config in config.get(DOMAIN, {}).get(CONF_DEVICES, {}).items():
        _LOGGER.debug("Importing configured %s", ipaddr)
        entry_config = {
            CONF_IP_ADDRESS: ipaddr,
            **device_config,
        }
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config,
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yeelight from a config entry."""

    if entry.data[CONF_DISCOVERY]:

        async def _initialize() -> None:
            scanner = YeelightScanner(hass, entry)
            unset = entry.add_update_listener(_async_update_listener)
            hass.data[DOMAIN][DATA_CONFIG_ENTRIES][entry.entry_id] = {
                DATA_SCANNER: scanner,
                DATA_UNSUB_UPDATE_LISTENER: unset,
            }

            # Wait for platform setup is important. Make sure callbacks are set up before scanning.
            await asyncio.gather(
                *[
                    hass.config_entries.async_forward_entry_setup(entry, component)
                    for component in PLATFORMS
                ]
            )

            await scanner.start_scan()

        hass.async_create_task(_initialize())

    else:

        # Move options from data for imported entries
        if not entry.options:
            hass.config_entries.async_update_entry(
                entry,
                data={
                    CONF_DISCOVERY: entry.data.get(CONF_DISCOVERY),
                    CONF_NAME: entry.data.get(CONF_NAME),
                    CONF_IP_ADDRESS: entry.data[CONF_IP_ADDRESS],
                },
                options={
                    CONF_MODEL: entry.data.get(CONF_MODEL, ""),
                    CONF_TRANSITION: entry.data.get(
                        CONF_TRANSITION, DEFAULT_TRANSITION
                    ),
                    CONF_MODE_MUSIC: entry.data.get(
                        CONF_MODE_MUSIC, DEFAULT_MODE_MUSIC
                    ),
                    CONF_SAVE_ON_CHANGE: entry.data.get(
                        CONF_SAVE_ON_CHANGE, DEFAULT_SAVE_ON_CHANGE
                    ),
                    CONF_NIGHTLIGHT_SWITCH: entry.data.get(
                        CONF_NIGHTLIGHT_SWITCH, DEFAULT_NIGHTLIGHT_SWITCH
                    ),
                },
            )

        config = {
            CONF_NAME: entry.data.get(CONF_NAME),  # Support name import from yaml
            **entry.options,
        }
        await _async_setup_device(hass, entry.data[CONF_IP_ADDRESS], config)
        unset = entry.add_update_listener(_async_update_listener)
        hass.data[DOMAIN][DATA_CONFIG_ENTRIES][entry.entry_id] = {
            DATA_UNSUB_UPDATE_LISTENER: unset,
        }
        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    if unload_ok:
        if entry.data[CONF_DISCOVERY]:
            data = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].pop(entry.entry_id)
            scanner = data[DATA_SCANNER]
            await scanner.stop_scan()
            for ipaddr in scanner.seen:
                hass.data[DOMAIN][DATA_DEVICES].pop(ipaddr)
            data[DATA_UNSUB_UPDATE_LISTENER]()
        else:
            hass.data[DOMAIN][DATA_DEVICES].pop(entry.data[CONF_IP_ADDRESS])
            data = hass.data[DOMAIN][DATA_CONFIG_ENTRIES].pop(entry.entry_id)
            data[DATA_UNSUB_UPDATE_LISTENER]()

    return unload_ok


async def _async_setup_device(
    hass: HomeAssistant,
    ipaddr: str,
    config: dict,
    discovery_config_entry: Optional[ConfigEntry] = None,
) -> None:
    # Set up device
    bulb = Bulb(ipaddr, model=config.get(CONF_MODEL) or None)
    capabilities = await hass.async_add_executor_job(bulb.get_capabilities)
    if capabilities is None:  # timeout
        _LOGGER.error("Failed to get capabilities from %s", ipaddr)
        raise ConfigEntryNotReady
    device = YeelightDevice(hass, ipaddr, config, bulb)
    await hass.async_add_executor_job(device.update)
    hass.data[DOMAIN][DATA_DEVICES][ipaddr] = device

    # Trigger platform setup
    if discovery_config_entry is not None:
        data = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][discovery_config_entry.entry_id]
        hass.async_create_task(data[DATA_SETUP_BINARY_SENSOR](ipaddr))
        hass.async_create_task(data[DATA_SETUP_LIGHT](ipaddr))


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class YeelightScanner:
    """Scan for Yeelight devices."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry):
        """Initialize class."""
        self._hass = hass
        self._config_entry = config_entry
        self._remove_listender = None
        self.seen = set()

    async def _async_scan(self, _):
        _LOGGER.debug("Yeelight scanning")
        # Run 3 times as packets can get lost
        for _ in range(3):
            devices = await self._hass.async_add_executor_job(discover_bulbs)
            for device in devices:
                unique_id = device["capabilities"]["id"]
                ipaddr = device["ip"]
                if ipaddr in self.seen:
                    continue
                self.seen.add(ipaddr)
                _LOGGER.debug("Yeelight discoevered at %s", ipaddr)

                # Initialize default configuration
                if unique_id not in self._config_entry.options:
                    # Temporarily disable update listener to avoid reload
                    self._hass.data[DOMAIN][DATA_CONFIG_ENTRIES][
                        self._config_entry.entry_id
                    ][DATA_UNSUB_UPDATE_LISTENER]()
                    self._hass.config_entries.async_update_entry(
                        self._config_entry,
                        options={
                            **self._config_entry.options,
                            unique_id: {
                                CONF_MODEL: "",
                                CONF_TRANSITION: DEFAULT_TRANSITION,
                                CONF_MODE_MUSIC: DEFAULT_MODE_MUSIC,
                                CONF_SAVE_ON_CHANGE: DEFAULT_SAVE_ON_CHANGE,
                                CONF_NIGHTLIGHT_SWITCH: DEFAULT_NIGHTLIGHT_SWITCH,
                            },
                        },
                    )
                    self._hass.data[DOMAIN][DATA_CONFIG_ENTRIES][
                        self._config_entry.entry_id
                    ][
                        DATA_UNSUB_UPDATE_LISTENER
                    ] = self._config_entry.add_update_listener(
                        _async_update_listener
                    )
                await _async_setup_device(
                    self._hass,
                    ipaddr,
                    self._config_entry.options[unique_id],
                    self._config_entry,
                )

    async def start_scan(self):
        """Start scanning for Yeelight devices."""
        _LOGGER.debug("Start scanning")
        await self._async_scan(None)
        self._remove_listender = async_track_time_interval(
            self._hass, self._async_scan, DISCOVERY_INTERVAL
        )

    async def stop_scan(self):
        """Stop scanning."""
        _LOGGER.debug("Stop scanning")
        if self._remove_listender is not None:
            self._remove_listender()
            self._remove_listender = None


class YeelightDevice:
    """Represents single Yeelight device."""

    def __init__(self, hass, ipaddr, config, bulb):
        """Initialize device."""
        self._hass = hass
        self._config = config
        self._ipaddr = ipaddr
        unique_id = bulb.capabilities.get("id")
        self._name = config.get(CONF_NAME) or f"yeelight_{bulb.model}_{unique_id}"
        self._bulb_device = bulb
        self._device_type = None
        self._available = False

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
        """Return configured/autodetected device model."""
        return self._bulb_device.model

    @property
    def fw_version(self):
        """Return the firmware version."""
        return self._bulb_device.capabilities.get("fw_ver")

    @property
    def is_nightlight_supported(self) -> bool:
        """
        Return true / false if nightlight is supported.

        Uses brightness as it appears to be supported in both ceiling and other lights.
        """

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

    @property
    def unique_id(self) -> Optional[str]:
        """Return a unique ID."""
        return self.bulb.capabilities.get("id")

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
        except BulbException as ex:
            if self._available:  # just inform once
                _LOGGER.error(
                    "Unable to update device %s, %s: %s", self.ipaddr, self.name, ex
                )
            self._available = False

        return self._available

    def _get_capabilities(self):
        """Request device capabilities."""
        try:
            self.bulb.get_capabilities()
            _LOGGER.debug(
                "Device %s, %s capabilities: %s",
                self.ipaddr,
                self.name,
                self.bulb.capabilities,
            )
        except BulbException as ex:
            _LOGGER.error(
                "Unable to get device capabilities %s, %s: %s",
                self.ipaddr,
                self.name,
                ex,
            )

    def update(self):
        """Update device properties and send data updated signal."""
        self._update_properties()
        dispatcher_send(self._hass, DATA_UPDATED.format(self._ipaddr))


class YeelightEntity(Entity):
    """Represents single Yeelight entity."""

    def __init__(self, device: YeelightDevice):
        """Initialize the entity."""
        self._device = device

    @property
    def device_info(self) -> dict:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._device.unique_id)},
            "name": self._device.name,
            "manufacturer": "Yeelight",
            "model": self._device.model,
            "sw_version": self._device.fw_version,
        }

    @property
    def available(self) -> bool:
        """Return if bulb is available."""
        return self._device.available

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    def update(self) -> None:
        """Update the entity."""
        self._device.update()
