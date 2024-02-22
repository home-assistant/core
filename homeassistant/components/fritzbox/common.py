"""Common functions for fritzbox integration."""

from homeassistant.core import HomeAssistant

from .const import CONF_COORDINATOR, DOMAIN
from .coordinator import FritzboxDataUpdateCoordinator


def get_coordinator(
    hass: HomeAssistant, config_entry_id: str
) -> FritzboxDataUpdateCoordinator:
    """Get coordinator for given config entry id."""
    coordinator: FritzboxDataUpdateCoordinator = hass.data[DOMAIN][config_entry_id][
        CONF_COORDINATOR
    ]
    return coordinator
