"""Helpers for automation integration."""

from homeassistant.components import blueprint
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "automation_blueprints"


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any automation references the blueprint."""
    from . import automations_with_blueprint  # pylint: disable=import-outside-toplevel

    return len(automations_with_blueprint(hass, blueprint_path)) > 0


async def _reload_blueprint_automations(
    hass: HomeAssistant, blueprint_path: str
) -> None:
    """Reload all automations that rely on a specific blueprint."""
    await hass.services.async_call(DOMAIN, SERVICE_RELOAD)


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> blueprint.DomainBlueprints:
    """Get automation blueprints."""
    # pylint: disable-next=import-outside-toplevel
    from .config import AUTOMATION_BLUEPRINT_SCHEMA

    return blueprint.DomainBlueprints(
        hass,
        DOMAIN,
        LOGGER,
        _blueprint_in_use,
        _reload_blueprint_automations,
        AUTOMATION_BLUEPRINT_SCHEMA,
    )
