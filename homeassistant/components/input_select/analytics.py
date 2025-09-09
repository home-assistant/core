"""Analytics platform."""

from homeassistant.components.analytics import EntityAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_entity_analytics(
    hass: HomeAssistant, entity_id: str, analytics: EntityAnalytics
) -> None:
    """Modify the analytics for an entity."""
    if analytics.capabilities is not None:
        analytics.capabilities["options"] = len(analytics.capabilities["options"])
