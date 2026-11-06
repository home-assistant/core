"""Constants for the WeatherFlow integration."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import WeatherFlowConfigEntry

DOMAIN = "weatherflow"
LOGGER = logging.getLogger(__package__)


def format_dispatch_call(config_entry: WeatherFlowConfigEntry) -> str:
    """Construct a dispatch call from a ConfigEntry."""
    return f"{config_entry.domain}_{config_entry.entry_id}_add"


ERROR_MSG_ADDRESS_IN_USE = "address_in_use"
ERROR_MSG_CANNOT_CONNECT = "cannot_connect"
ERROR_MSG_NO_DEVICE_FOUND = "no_device_found"
