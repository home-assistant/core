"""Provides triggers for buttons."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import StatelessEntityTriggerBase, Trigger

from . import DOMAIN


class ButtonPressedTrigger(StatelessEntityTriggerBase):
    """Trigger for button entity presses."""

    _domain_specs = {DOMAIN: DomainSpec()}


TRIGGERS: dict[str, type[Trigger]] = {
    "pressed": ButtonPressedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for buttons."""
    return TRIGGERS
