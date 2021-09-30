"""Helpers for automation integration."""
from homeassistant.components.blueprint import DomainBlueprints
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "script_blueprints"


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> DomainBlueprints:
    """Get script blueprints."""
    return DomainBlueprints(hass, DOMAIN, LOGGER)
