"""Provides conditions for datetime."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import Condition, make_entity_datetime_condition

from .const import DOMAIN

CONDITIONS: dict[str, type[Condition]] = {
    "is_before": make_entity_datetime_condition(
        {
            DOMAIN: DomainSpec(),
            "sensor": DomainSpec(device_class="timestamp"),
        },
        primary_entities_only=False,
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the conditions for datetime."""
    return CONDITIONS
