"""The Dyson integration."""
import asyncio
from functools import partial
import logging

from libpurecool.dyson import DysonAccount
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry, ConfigEntryNotReady
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DATA_DEVICES = "devices"
DATA_UNSUB = "unsub"

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
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Dyson from a config entry."""
    _LOGGER.info("Creating new Dyson component")
    _LOGGER.debug("Start set up")

    # Move device list from data to options for imported entries
    if CONF_DEVICES in entry.data:
        data = {**entry.data}
        options = data.pop(CONF_DEVICES)
        hass.config_entries.async_update_entry(entry, data=data, options=options)

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

    dyson_devices = await hass.async_add_executor_job(dyson_account.devices)

    # Update device list in options
    options = {}
    for device in dyson_devices:
        if device.serial not in entry.options:
            options[device.serial] = ""  # Empty string means discovery
        else:
            options[device.serial] = entry.options[device.serial]
    hass.config_entries.async_update_entry(entry, options=options)

    # Listen to options update
    unsub = entry.add_update_listener(async_update_listener)
    hass.data[DOMAIN][entry.entry_id] = {DATA_UNSUB: unsub}

    _LOGGER.debug(entry.options)
    data_devices = []
    for device in dyson_devices:
        if entry.options[device.serial]:
            # Manually set up with IP address
            try:
                connected = await hass.async_add_executor_job(
                    partial(device.connect, entry.options[device.serial])
                )
                if connected:
                    _LOGGER.info("Connected to device %s", device)
                    data_devices.append(device)
                else:
                    _LOGGER.warning("Unable to connect to device %s", device)
            except OSError as ose:
                _LOGGER.error(
                    "Unable to connect to device %s: %s",
                    str(device.network_device),
                    str(ose),
                )
        else:
            # Discovery
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
    hass.data[DOMAIN][entry.entry_id][DATA_DEVICES] = data_devices

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
        data = hass.data[DOMAIN].pop(entry.entry_id)
        data[DATA_UNSUB]()

    _LOGGER.debug("Finish unload")
    return unload_ok


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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
