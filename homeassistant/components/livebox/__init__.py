"""Orange Livebox."""
import logging
from datetime import timedelta
import voluptuous as vol

from aiosysbus import Sysbus
from aiosysbus.exceptions import HttpRequestError, AuthorizationError

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.discovery import async_load_platform

from .const import (
    DOMAIN,
    DEFAULT_USERNAME,
    DEFAULT_HOST,
    DEFAULT_PORT,
    CONF_ALLOW_TRACKER,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                # Validate as IP address and then convert back to a string.
                vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
                vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCAN_INTERVAL = timedelta(minutes=5)


async def async_setup(hass, config):
    """Load configuration for Livebox component."""

    if not hass.config_entries.async_entries(DOMAIN) and DOMAIN in config:
        livebox_config = config[DOMAIN]
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": config.SOURCE_IMPORT}, data=livebox_config
            )
        )
    return True


async def async_setup_entry(hass, entry):
    """Set up Livebox as config entry."""

    box = await async_connect(entry)
    hass.data[DOMAIN] = box
    config = (await box.system.get_deviceinfo())["status"]

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, config["SerialNumber"])},
        manufacturer=config["Manufacturer"],
        name=config["ProductClass"],
        model=config["ModelName"],
        sw_version=config["SoftwareVersion"],
    )

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "binary_sensor")
    )

    hass.async_create_task(
        async_load_platform(hass, "device_tracker", DOMAIN, {}, config)
    )

    if not entry.options:
        options = {
            CONF_ALLOW_TRACKER: entry.data["options"].get(CONF_ALLOW_TRACKER, True)
        }
        hass.config_entries.async_update_entry(entry, options=options)

    if entry.options[CONF_ALLOW_TRACKER]:
        hass.async_create_task(
            async_load_platform(hass, "device_tracker", DOMAIN, {}, config)
        )

    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""

    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")
    # ~ await hass.config_entries.async_forward_entry_unload(entry, "device_tracker")
    box = hass.data[DOMAIN]
    await box.close()

    return True


async def async_connect(entry):
    """Connect at box."""

    box = Sysbus()
    try:
        await box.open(
            host=entry.data["host"],
            port=entry.data["port"],
            username=entry.data["username"],
            password=entry.data["password"],
        )
    except AuthorizationError:
        _LOGGER.error("User or password incorrect")
        return False
    except HttpRequestError:
        _LOGGER.error("Http Request error to Livebox")
        return False

    return box
