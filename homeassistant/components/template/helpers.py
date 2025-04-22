"""Helpers for template integration."""

import logging

from homeassistant.components import blueprint
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.singleton import singleton

from .const import DOMAIN, TEMPLATE_BLUEPRINT_SCHEMA
from .entity import AbstractTemplateEntity

DATA_BLUEPRINTS = "template_blueprints"

LOGGER = logging.getLogger(__name__)


@callback
def templates_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all template entity ids that reference the blueprint."""
    return [
        entity_id
        for platform in async_get_platforms(hass, DOMAIN)
        for entity_id, template_entity in platform.entities.items()
        if isinstance(template_entity, AbstractTemplateEntity)
        and template_entity.referenced_blueprint == blueprint_path
    ]


@callback
def blueprint_in_template(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the blueprint the template entity is based on or None."""
    for platform in async_get_platforms(hass, DOMAIN):
        if isinstance(
            (template_entity := platform.entities.get(entity_id)),
            AbstractTemplateEntity,
        ):
            return template_entity.referenced_blueprint
    return None


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any template references the blueprint."""
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
