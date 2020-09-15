"""The Dyson integration."""
import asyncio
from functools import partial
import logging

from libpurecool.dyson import DysonAccount
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_LANGUAGE = "language"
CONF_RETRY = "retry"

DEFAULT_TIMEOUT = 5
DEFAULT_RETRY = 10
PLATFORMS = ["sensor", "fan", "vacuum", "climate", "air_quality"]

DOMAIN = "dyson"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Required(CONF_LANGUAGE): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
                vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): cv.positive_int,
                vol.Optional(CONF_DEVICES, default=[]): vol.All(cv.ensure_list, [dict]),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Dyson component."""
    # TODO: import
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Dyson from a config entry."""
    _LOGGER.info("Creating new Dyson component")

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    dyson_account = DysonAccount(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_LANGUAGE],
    )

    logged = await hass.async_add_executor_job(dyson_account.login)

    timeout = DEFAULT_TIMEOUT
    retry = DEFAULT_RETRY

    if not logged:
        _LOGGER.error("Not connected to Dyson account. Unable to add devices")
        raise ConfigEntryNotReady

    _LOGGER.info("Connected to Dyson account")
    data_devices = []
    dyson_devices = await hass.async_add_executor_job(dyson_account.devices)
    if CONF_DEVICES in entry.data and entry.data.get(CONF_DEVICES):
        configured_devices = entry.data.get(CONF_DEVICES)
        for device in configured_devices:
            dyson_device = next(
                (d for d in dyson_devices if d.serial == device["device_id"]), None
            )
            if dyson_device:
                try:
                    connected = await hass.async_add_executor_job(
                        partial(dyson_device.connect, device["device_ip"])
                    )
                    if connected:
                        _LOGGER.info("Connected to device %s", dyson_device)
                        data_devices.append(dyson_device)
                    else:
                        _LOGGER.warning("Unable to connect to device %s", dyson_device)
                except OSError as ose:
                    _LOGGER.error(
                        "Unable to connect to device %s: %s",
                        str(dyson_device.network_device),
                        str(ose),
                    )
            else:
                _LOGGER.warning(
                    "Unable to find device %s in Dyson account", device["device_id"]
                )
    else:
        # Not yet reliable
        for device in dyson_devices:
            _LOGGER.info(
                "Trying to connect to device %s with timeout=%i and retry=%i",
                device,
                timeout,
                retry,
            )
            connected = await hass.async_add_executor_job(
                partial(device.auto_connect, timeout, retry)
            )
            if connected:
                _LOGGER.info("Connected to device %s", device)
                data_devices.append(device)
            else:
                _LOGGER.warning("Unable to connect to device %s", device)

    hass.data[DOMAIN][entry.entry_id] = data_devices

    # Start fan/sensors components
    if data_devices:
        _LOGGER.debug("Starting sensor/fan components")
        for platform in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, platform)
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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class DysonEntity(Entity):
    """Represents a dyson entity."""

    def __init__(self, device):
        """Initialize the entity."""
        self._device = device

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self.hass.async_add_job(self._device.add_message_listener, self.on_message)

    def on_message(self, message):
        """Call when new messages received."""

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the display name of the entity."""
        return self._device.name

    @property
    def unique_id(self):
        """Return the unique id of the entity."""
        return self._device.serial

    @property
    def device_info(self):
        """Return the device information of the entity."""
        return {
            "identifiers": {(DOMAIN, self._device.serial)},
            "name": self._device.name,
            "manufacturer": "Dyson",
            "sw_version": self._device.version,
        }
