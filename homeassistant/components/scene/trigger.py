"""Provides triggers for scenes."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import StatelessEntityTriggerBase, Trigger

from . import DOMAIN


class SceneActivatedTrigger(StatelessEntityTriggerBase):
    """Trigger for scene entity activations."""

    _domain_specs = {DOMAIN: DomainSpec()}


TRIGGERS: dict[str, type[Trigger]] = {
    "activated": SceneActivatedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for scenes."""
    return TRIGGERS
