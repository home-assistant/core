"""Support for Xiaomi Yeelight WiFi color bulb."""
from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from ipaddress import IPv4Address, IPv6Address
import logging
from urllib.parse import urlparse

from async_upnp_client.search import SsdpSearchListener
import voluptuous as vol
from yeelight import BulbException
from yeelight.aio import KEY_CONNECTED, AsyncBulb

from homeassistant import config_entries
from homeassistant.components import network
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.const import (
    CONF_DEVICES,
    CONF_HOST,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

STATE_CHANGE_TIME = 0.40  # seconds
POWER_STATE_CHANGE_TIME = 1  # seconds

DOMAIN = "yeelight"
DATA_YEELIGHT = DOMAIN
DATA_UPDATED = "yeelight_{}_data_updated"

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

DATA_CONFIG_ENTRIES = "config_entries"
DATA_CUSTOM_EFFECTS = "custom_effects"
DATA_DEVICE = "device"
DATA_REMOVE_INIT_DISPATCHER = "remove_init_dispatcher"
DATA_PLATFORMS_LOADED = "platforms_loaded"

ATTR_COUNT = "count"
ATTR_ACTION = "action"
ATTR_TRANSITIONS = "transitions"
ATTR_MODE_MUSIC = "music_mode"

ACTION_RECOVER = "recover"
ACTION_STAY = "stay"
ACTION_OFF = "off"

ACTIVE_MODE_NIGHTLIGHT = 1
ACTIVE_COLOR_FLOWING = 1

NIGHTLIGHT_SWITCH_TYPE_LIGHT = "light"

DISCOVERY_INTERVAL = timedelta(seconds=60)
SSDP_TARGET = ("239.255.255.250", 1982)
SSDP_ST = "wifi_bulb"
DISCOVERY_ATTEMPTS = 3
DISCOVERY_SEARCH_INTERVAL = timedelta(seconds=2)
DISCOVERY_TIMEOUT = 2


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


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Yeelight bulbs."""
    conf = config.get(DOMAIN, {})
    hass.data[DOMAIN] = {
        DATA_CUSTOM_EFFECTS: conf.get(CONF_CUSTOM_EFFECTS, {}),
        DATA_CONFIG_ENTRIES: {},
    }
    # Make sure the scanner is always started in case we are
    # going to retry via ConfigEntryNotReady and the bulb has changed
    # ip
    scanner = YeelightScanner.async_get(hass)
    await scanner.async_setup()

    # Import manually configured devices
    for host, device_config in config.get(DOMAIN, {}).get(CONF_DEVICES, {}).items():
        _LOGGER.debug("Importing configured %s", host)
        entry_config = {CONF_HOST: host, **device_config}
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=entry_config
            )
        )

    return True


async def _async_initialize(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device: YeelightDevice,
) -> None:
    entry_data = hass.data[DOMAIN][DATA_CONFIG_ENTRIES][entry.entry_id] = {}
    await device.async_setup()
    entry_data[DATA_DEVICE] = device

    if (
        device.capabilities
        and entry.options.get(CONF_MODEL) != device.capabilities["model"]
    ):
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_MODEL: device.capabilities["model"]}
        )

    # fetch initial state
    await device.async_update()
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))


@callback
def _async_normalize_config_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Move options from data for imported entries.

    Initialize options with default values for other entries.

    Copy the unique id to CONF_ID if it is missing
    """
    if not entry.options:
        hass.config_entries.async_update_entry(
            entry,
            data={
                CONF_HOST: entry.data.get(CONF_HOST),
                CONF_ID: entry.data.get(CONF_ID) or entry.unique_id,
            },
            options={
                CONF_NAME: entry.data.get(CONF_NAME, ""),
                CONF_MODEL: entry.data.get(CONF_MODEL, ""),
                CONF_TRANSITION: entry.data.get(CONF_TRANSITION, DEFAULT_TRANSITION),
                CONF_MODE_MUSIC: entry.data.get(CONF_MODE_MUSIC, DEFAULT_MODE_MUSIC),
                CONF_SAVE_ON_CHANGE: entry.data.get(
                    CONF_SAVE_ON_CHANGE, DEFAULT_SAVE_ON_CHANGE
                ),
                CONF_NIGHTLIGHT_SWITCH: entry.data.get(
                    CONF_NIGHTLIGHT_SWITCH, DEFAULT_NIGHTLIGHT_SWITCH
                ),
            },
            unique_id=entry.unique_id or entry.data.get(CONF_ID),
        )
    elif entry.unique_id and not entry.data.get(CONF_ID):
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_HOST: entry.data.get(CONF_HOST), CONF_ID: entry.unique_id},
        )
    elif entry.data.get(CONF_ID) and not entry.unique_id:
        hass.config_entries.async_update_entry(
            entry,
            unique_id=entry.data[CONF_ID],
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yeelight from a config entry."""
    _async_normalize_config_entry(hass, entry)

    if not entry.data.get(CONF_HOST):
        bulb_id = async_format_id(entry.data.get(CONF_ID, entry.unique_id))
        raise ConfigEntryNotReady(f"Waiting for {bulb_id} to be discovered")

    try:
        device = await _async_get_device(hass, entry.data[CONF_HOST], entry)
        await _async_initialize(hass, entry, device)
    except (asyncio.TimeoutError, OSError, BulbException) as ex:
        raise ConfigEntryNotReady from ex

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    data_config_entries = hass.data[DOMAIN][DATA_CONFIG_ENTRIES]
    data_config_entries.pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


@callback
def async_format_model(model: str) -> str:
    """Generate a more human readable model."""
    return model.replace("_", " ").title()


@callback
def async_format_id(id_: str) -> str:
    """Generate a more human readable id."""
    return hex(int(id_, 16)) if id_ else "None"


@callback
def async_format_model_id(model: str, id_: str) -> str:
    """Generate a more human readable name."""
    return f"{async_format_model(model)} {async_format_id(id_)}"


@callback
def _async_unique_name(capabilities: dict) -> str:
    """Generate name from capabilities."""
    model_id = async_format_model_id(capabilities["model"], capabilities["id"])
    return f"Yeelight {model_id}"


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class YeelightScanner:
    """Scan for Yeelight devices."""

    _scanner = None

    @classmethod
    @callback
    def async_get(cls, hass: HomeAssistant):
        """Get scanner instance."""
        if cls._scanner is None:
            cls._scanner = cls(hass)
        return cls._scanner

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize class."""
        self._hass = hass
        self._host_discovered_events = {}
        self._unique_id_capabilities = {}
        self._host_capabilities = {}
        self._track_interval = None
        self._listeners = []
        self._connected_events = []

    async def async_setup(self):
        """Set up the scanner."""
        if self._connected_events:
            await self._async_wait_connected()
            return

        for idx, source_ip in enumerate(await self._async_build_source_set()):
            self._connected_events.append(asyncio.Event())

            def _wrap_async_connected_idx(idx):
                """Create a function to capture the idx cell variable."""

                async def _async_connected():
                    self._connected_events[idx].set()

                return _async_connected

            self._listeners.append(
                SsdpSearchListener(
                    async_callback=self._async_process_entry,
                    service_type=SSDP_ST,
                    target=SSDP_TARGET,
                    source_ip=source_ip,
                    async_connect_callback=_wrap_async_connected_idx(idx),
                )
            )

        results = await asyncio.gather(
            *(listener.async_start() for listener in self._listeners),
            return_exceptions=True,
        )
        failed_listeners = []
        for idx, result in enumerate(results):
            if not isinstance(result, Exception):
                continue
            _LOGGER.warning(
                "Failed to setup listener for %s: %s",
                self._listeners[idx].source_ip,
                result,
            )
            failed_listeners.append(self._listeners[idx])
            self._connected_events[idx].set()

        for listener in failed_listeners:
            self._listeners.remove(listener)

        await self._async_wait_connected()
        self._track_interval = async_track_time_interval(
            self._hass, self.async_scan, DISCOVERY_INTERVAL
        )
        self.async_scan()

    async def _async_wait_connected(self):
        """Wait for the listeners to be up and connected."""
        await asyncio.gather(*(event.wait() for event in self._connected_events))

    async def _async_build_source_set(self) -> set[IPv4Address]:
        """Build the list of ssdp sources."""
        adapters = await network.async_get_adapters(self._hass)
        sources: set[IPv4Address] = set()
        if network.async_only_default_interface_enabled(adapters):
            sources.add(IPv4Address("0.0.0.0"))
            return sources

        return {
            source_ip
            for source_ip in await network.async_get_enabled_source_ips(self._hass)
            if not source_ip.is_loopback and not isinstance(source_ip, IPv6Address)
        }

    async def async_discover(self):
        """Discover bulbs."""
        _LOGGER.debug("Yeelight discover with interval %s", DISCOVERY_SEARCH_INTERVAL)
        await self.async_setup()
        for _ in range(DISCOVERY_ATTEMPTS):
            self.async_scan()
            await asyncio.sleep(DISCOVERY_SEARCH_INTERVAL.total_seconds())
        return self._unique_id_capabilities.values()

    @callback
    def async_scan(self, *_):
        """Send discovery packets."""
        _LOGGER.debug("Yeelight scanning")
        for listener in self._listeners:
            listener.async_search()

    async def async_get_capabilities(self, host):
        """Get capabilities via SSDP."""
        if host in self._host_capabilities:
            return self._host_capabilities[host]

        host_event = asyncio.Event()
        self._host_discovered_events.setdefault(host, []).append(host_event)
        await self.async_setup()

        for listener in self._listeners:
            listener.async_search((host, SSDP_TARGET[1]))

        with contextlib.suppress(asyncio.TimeoutError):
            await asyncio.wait_for(host_event.wait(), timeout=DISCOVERY_TIMEOUT)

        self._host_discovered_events[host].remove(host_event)
        return self._host_capabilities.get(host)

    def _async_discovered_by_ssdp(self, response):
        @callback
        def _async_start_flow(*_):
            asyncio.create_task(
                self._hass.config_entries.flow.async_init(
                    DOMAIN,
                    context={"source": config_entries.SOURCE_SSDP},
                    data=response,
                )
            )

        # Delay starting the flow in case the discovery is the result
        # of another discovery
        async_call_later(self._hass, 1, _async_start_flow)

    async def _async_process_entry(self, response):
        """Process a discovery."""
        _LOGGER.debug("Discovered via SSDP: %s", response)
        unique_id = response["id"]
        host = urlparse(response["location"]).hostname
        current_entry = self._unique_id_capabilities.get(unique_id)
        # Make sure we handle ip changes
        if not current_entry or host != urlparse(current_entry["location"]).hostname:
            _LOGGER.debug("Yeelight discovered with %s", response)
            self._async_discovered_by_ssdp(response)
        self._host_capabilities[host] = response
        self._unique_id_capabilities[unique_id] = response
        for event in self._host_discovered_events.get(host, []):
            event.set()


def update_needs_bg_power_workaround(data):
    """Check if a push update needs the bg_power workaround.

    Some devices will push the incorrect state for bg_power.

    To work around this any time we are pushed an update
    with bg_power, we force poll state which will be correct.
    """
    return "bg_power" in data


class YeelightDevice:
    """Represents single Yeelight device."""

    def __init__(self, hass, host, config, bulb):
        """Initialize device."""
        self._hass = hass
        self._config = config
        self._host = host
        self._bulb_device = bulb
        self.capabilities = {}
        self._device_type = None
        self._available = True
        self._initialized = False
        self._did_first_update = False
        self._name = None

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
    def host(self):
        """Return hostname."""
        return self._host

    @property
    def available(self):
        """Return true is device is available."""
        return self._available

    @callback
    def async_mark_unavailable(self):
        """Set unavailable on api call failure due to a network issue."""
        self._available = False

    @property
    def model(self):
        """Return configured/autodetected device model."""
        return self._bulb_device.model or self.capabilities.get("model")

    @property
    def fw_version(self):
        """Return the firmware version."""
        return self.capabilities.get("fw_ver")

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
        # Only ceiling lights have active_mode, from SDK docs:
        # active_mode 0: daylight mode / 1: moonlight mode (ceiling light only)
        if self._active_mode is not None:
            return int(self._active_mode) == ACTIVE_MODE_NIGHTLIGHT

        if self._nightlight_brightness is not None:
            return int(self._nightlight_brightness) > 0

        return False

    @property
    def is_color_flow_enabled(self) -> bool:
        """Return true / false if color flow is currently running."""
        return int(self._color_flow) == ACTIVE_COLOR_FLOWING

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

    async def _async_update_properties(self):
        """Read new properties from the device."""
        try:
            await self.bulb.async_get_properties(UPDATE_REQUEST_PROPERTIES)
            self._available = True
            if not self._initialized:
                self._initialized = True
        except OSError as ex:
            if self._available:  # just inform once
                _LOGGER.error(
                    "Unable to update device %s, %s: %s", self._host, self.name, ex
                )
            self._available = False
        except asyncio.TimeoutError as ex:
            _LOGGER.debug(
                "timed out while trying to update device %s, %s: %s",
                self._host,
                self.name,
                ex,
            )
        except BulbException as ex:
            _LOGGER.debug(
                "Unable to update device %s, %s: %s", self._host, self.name, ex
            )

    async def async_setup(self):
        """Fetch capabilities and setup name if available."""
        scanner = YeelightScanner.async_get(self._hass)
        self.capabilities = await scanner.async_get_capabilities(self._host) or {}
        if self.capabilities:
            self._bulb_device.set_capabilities(self.capabilities)
        if name := self._config.get(CONF_NAME):
            # Override default name when name is set in config
            self._name = name
        elif self.capabilities:
            # Generate name from model and id when capabilities is available
            self._name = _async_unique_name(self.capabilities)
        else:
            self._name = self._host  # Default name is host

    async def async_update(self, force=False):
        """Update device properties and send data updated signal."""
        self._did_first_update = True
        if not force and self._initialized and self._available:
            # No need to poll unless force, already connected
            return
        await self._async_update_properties()
        async_dispatcher_send(self._hass, DATA_UPDATED.format(self._host))

    async def _async_forced_update(self, _now):
        """Call a forced update."""
        await self.async_update(True)

    @callback
    def async_update_callback(self, data):
        """Update push from device."""
        was_available = self._available
        self._available = data.get(KEY_CONNECTED, True)
        if update_needs_bg_power_workaround(data) or (
            self._did_first_update and not was_available and self._available
        ):
            # On reconnect the properties may be out of sync
            #
            # If the device drops the connection right away, we do not want to
            # do a property resync via async_update since its about
            # to be called when async_setup_entry reaches the end of the
            # function
            #
            async_call_later(self._hass, STATE_CHANGE_TIME, self._async_forced_update)
        async_dispatcher_send(self._hass, DATA_UPDATED.format(self._host))


class YeelightEntity(Entity):
    """Represents single Yeelight entity."""

    def __init__(self, device: YeelightDevice, entry: ConfigEntry) -> None:
        """Initialize the entity."""
        self._device = device
        self._unique_id = entry.unique_id or entry.entry_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID."""
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._unique_id)},
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

    async def async_update(self) -> None:
        """Update the entity."""
        await self._device.async_update()


async def _async_get_device(
    hass: HomeAssistant, host: str, entry: ConfigEntry
) -> YeelightDevice:
    # Get model from config and capabilities
    model = entry.options.get(CONF_MODEL)

    # Set up device
    bulb = AsyncBulb(host, model=model or None)

    device = YeelightDevice(hass, host, entry.options, bulb)
    # start listening for local pushes
    await device.bulb.async_listen(device.async_update_callback)

    # register stop callback to shutdown listening for local pushes
    async def async_stop_listen_task(event):
        """Stop listen task."""
        _LOGGER.debug("Shutting down Yeelight Listener (stop event)")
        await device.bulb.async_stop_listening()

    @callback
    def _async_stop_listen_on_unload():
        """Stop listen task."""
        _LOGGER.debug("Shutting down Yeelight Listener (unload)")
        hass.async_create_task(device.bulb.async_stop_listening())

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_listen_task)
    )
    entry.async_on_unload(_async_stop_listen_on_unload)

    return device
