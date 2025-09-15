"""Analytics platform."""

from homeassistant.components.analytics import AnalyticsConfig
from homeassistant.core import HomeAssistant


async def async_modify_analytics(hass: HomeAssistant, config: AnalyticsConfig) -> None:
    """Modify the analytics."""
    for entity_analytics in config.entities.values():
        if entity_analytics.capabilities is not None:
            entity_analytics.capabilities["options"] = len(
                entity_analytics.capabilities["options"]
            )
