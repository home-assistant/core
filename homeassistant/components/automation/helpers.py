"""Helpers for automation integration."""
from homeassistant.components import blueprint
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "automation_blueprints"


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> blueprint.DomainBlueprints:
    """Get automation blueprints."""
    return blueprint.DomainBlueprints(hass, DOMAIN, LOGGER)
