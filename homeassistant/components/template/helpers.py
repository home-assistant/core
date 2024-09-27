"""Helpers for template integration."""

import logging

from homeassistant.components import blueprint
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, TEMPLATE_BLUEPRINT_SCHEMA

DATA_BLUEPRINTS = "template_blueprints"

LOGGER = logging.getLogger(__name__)


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any template references the blueprint."""
    from . import templates_with_blueprint  # pylint: disable=import-outside-toplevel

    return len(templates_with_blueprint(hass, blueprint_path)) > 0


async def _reload_blueprint_templates(hass: HomeAssistant, blueprint_path: str) -> None:
    """Reload all templates that rely on a specific blueprint."""
    await hass.services.async_call(DOMAIN, SERVICE_RELOAD)


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> blueprint.DomainBlueprints:
    """Get template blueprints."""
    return blueprint.DomainBlueprints(
        hass,
        DOMAIN,
        LOGGER,
        _blueprint_in_use,
        _reload_blueprint_templates,
        TEMPLATE_BLUEPRINT_SCHEMA,
    )
