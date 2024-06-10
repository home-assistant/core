"""Helpers for automation integration."""

from homeassistant.components.blueprint import DomainBlueprints
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "script_blueprints"


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any script references the blueprint."""
    from . import scripts_with_blueprint  # pylint: disable=import-outside-toplevel

    return len(scripts_with_blueprint(hass, blueprint_path)) > 0


async def _reload_blueprint_scripts(hass: HomeAssistant, blueprint_path: str) -> None:
    """Reload all script that rely on a specific blueprint."""
    await hass.services.async_call(DOMAIN, SERVICE_RELOAD)


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> DomainBlueprints:
    """Get script blueprints."""
    return DomainBlueprints(
        hass, DOMAIN, LOGGER, _blueprint_in_use, _reload_blueprint_scripts
    )
