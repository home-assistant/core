"""Provides triggers for text and input_text entities."""

from homeassistant.components.input_text import DOMAIN as INPUT_TEXT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityTriggerBase,
    Trigger,
)

from .const import DOMAIN


class TextChangedTrigger(EntityTriggerBase):
    """Trigger for text and input_text entities when their content changes."""

    _domain_specs = {DOMAIN: DomainSpec(), INPUT_TEXT_DOMAIN: DomainSpec()}
    _schema = ENTITY_STATE_TRIGGER_SCHEMA


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": TextChangedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for text and input_text entities."""
    return TRIGGERS
