"""Analytics platform."""

from homeassistant.components.analytics import (
    AnalyticsInput,
    AnalyticsModifications,
    EntityAnalyticsModifications,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def async_modify_analytics(
    hass: HomeAssistant, analytics_input: AnalyticsInput
) -> AnalyticsModifications:
    """Modify the analytics."""
    ent_reg = er.async_get(hass)

    entities: dict[str, EntityAnalyticsModifications] = {}
    for entity_id in analytics_input.entity_ids:
        entity_entry = ent_reg.entities[entity_id]
        if entity_entry.capabilities is not None:
            capabilities = dict(entity_entry.capabilities)
            capabilities["options"] = len(capabilities["options"])
            entities[entity_id] = EntityAnalyticsModifications(
                capabilities=capabilities
            )

    return AnalyticsModifications(entities=entities)
