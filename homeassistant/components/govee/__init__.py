"""Support for Govee Heater integration."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
import homeassistant.helpers.config_validation as cv

from .const import CONF_API_KEY, CONF_DEVICE_ID, CONF_SKU, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_DEVICE_ID): cv.string,
                vol.Required(CONF_SKU): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up Govee Heater from configuration.yaml."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {
        CONF_API_KEY: config[DOMAIN][CONF_API_KEY],
        CONF_DEVICE_ID: config[DOMAIN][CONF_DEVICE_ID],
        CONF_SKU: config[DOMAIN][CONF_SKU],
    }

    hass.helpers.discovery.load_platform("switch", DOMAIN, {}, config)

    return True


def _handle_auth(api_key: str) -> None:
    """Validate API key and raise appropriate exceptions."""
    if not api_key:
        raise ConfigEntryAuthFailed("Invalid API key")


def _handle_connection(connected: bool) -> None:
    """Validate connection and raise appropriate exceptions."""
    if not connected:
        raise ConfigEntryNotReady("Unable to connect to Govee API")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Govee Heater from a config entry."""
    try:
        # Perform setup tasks
        # Example: Validate API key or perform initial connection
        api_key = entry.data[CONF_API_KEY]
        _handle_auth(api_key)

        # Simulate a temporary error
        connected = await validate_connection(api_key)
        _handle_connection(connected)

        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][entry.entry_id] = entry.data
        entry.runtime_data = {"some_key": "some_value"}

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except ConfigEntryAuthFailed as err:
        _LOGGER.error("Authentication failed: %s", err)
        raise
    except ConfigEntryNotReady as err:
        _LOGGER.warning("Temporary setup failure: %s", err)
        raise
    except Exception as err:
        _LOGGER.error("Unexpected error: %s", err)
        raise ConfigEntryError("Unexpected error during setup") from err

    return True  # We only reach here if no exceptions were raised


async def validate_connection(_api_key: str) -> bool:
    """Validate the connection to the Govee API."""
    # Implement the actual connection validation logic here
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "switch")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
