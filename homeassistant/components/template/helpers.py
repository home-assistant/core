"""Helpers for template integration."""
from homeassistant.components.blueprint import DomainBlueprints
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.singleton import singleton
from homeassistant.helpers.template_entity import TemplateEntity

from .const import DOMAIN, LOGGER

DATA_BLUEPRINTS = "template_blueprints"


@callback
def templates_with_blueprint(hass: HomeAssistant, blueprint_path: str) -> list[str]:
    """Return all templates that reference the blueprint."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[TemplateEntity] = hass.data[DOMAIN]

    return [
        template_entity.entity_id
        for template_entity in component.entities
        if template_entity.referenced_blueprint == blueprint_path
    ]


def _blueprint_in_use(hass: HomeAssistant, blueprint_path: str) -> bool:
    """Return True if any template references the blueprint."""

    return len(templates_with_blueprint(hass, blueprint_path)) > 0


@singleton(DATA_BLUEPRINTS)
@callback
def async_get_blueprints(hass: HomeAssistant) -> DomainBlueprints:
    """Get script blueprints."""
    return DomainBlueprints(hass, DOMAIN, LOGGER, _blueprint_in_use)
