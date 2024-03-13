"""Constants for the WeatherFlow integration."""

import logging

from homeassistant.config_entries import ConfigEntry

DOMAIN = "weatherflow"
LOGGER = logging.getLogger(__package__)


def format_dispatch_call(config_entry: ConfigEntry) -> str:
    """Construct a dispatch call from a ConfigEntry."""
    return f"{config_entry.domain}_{config_entry.entry_id}_add"


ERROR_MSG_ADDRESS_IN_USE = "address_in_use"
ERROR_MSG_CANNOT_CONNECT = "cannot_connect"
ERROR_MSG_NO_DEVICE_FOUND = "no_device_found"
