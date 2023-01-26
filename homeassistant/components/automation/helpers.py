"""Helpers for automation integration."""
from homeassistant.components import blueprint
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "automation_blueprints"


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any automation references the blueprint."""
    from . import automations_with_blueprint  # pylint: disable=import-outside-toplevel

    return len(automations_with_blueprint(hass, blueprint_path)) > 0


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> blueprint.DomainBlueprints:
    """Get automation blueprints."""
    return blueprint.DomainBlueprints(hass, DOMAIN, LOGGER, _blueprint_in_use)
