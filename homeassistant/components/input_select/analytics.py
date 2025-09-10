"""Analytics platform."""

from homeassistant.components.analytics import EntityAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_entity_analytics(
    hass: HomeAssistant, entities_analytics: dict[str, EntityAnalytics]
) -> None:
    """Modify the analytics for entities."""
    for entity_analytics in entities_analytics.values():
        if entity_analytics.capabilities is not None:
            entity_analytics.capabilities["options"] = len(
                entity_analytics.capabilities["options"]
            )
