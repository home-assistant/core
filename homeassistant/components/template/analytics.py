"""Analytics platform."""

from homeassistant.components.analytics import (
    AnalyticsInput,
    AnalyticsModifications,
    EntityAnalyticsModifications,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er

FILTERED_PLATFORM_CAPABILITY: dict[str, str] = {
    Platform.FAN: "preset_modes",
    Platform.SELECT: "options",
}


async def async_modify_analytics(
    hass: HomeAssistant, analytics_input: AnalyticsInput
) -> AnalyticsModifications:
    """Modify the analytics."""
    ent_reg = er.async_get(hass)

    entities: dict[str, EntityAnalyticsModifications] = {}
    for entity_id in analytics_input.entity_ids:
        platform = split_entity_id(entity_id)[0]
        if platform not in FILTERED_PLATFORM_CAPABILITY:
            continue

        entity_entry = ent_reg.entities[entity_id]
        if entity_entry.capabilities is not None:
            filtered_capability = FILTERED_PLATFORM_CAPABILITY[platform]
            if filtered_capability not in entity_entry.capabilities:
                continue

            capabilities = dict(entity_entry.capabilities)
            capabilities[filtered_capability] = len(capabilities[filtered_capability])

            entities[entity_id] = EntityAnalyticsModifications(
                capabilities=capabilities
            )

    return AnalyticsModifications(entities=entities)
