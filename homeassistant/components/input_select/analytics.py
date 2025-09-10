"""Analytics platform."""

from homeassistant.components.analytics import DeviceAnalytics, EntityAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_analytics(
    hass: HomeAssistant,
    devices_analytics: dict[str, DeviceAnalytics],
    entities_analytics: dict[str, EntityAnalytics],
) -> None:
    """Modify the analytics."""
    for entity_analytics in entities_analytics.values():
        if entity_analytics.capabilities is not None:
            entity_analytics.capabilities["options"] = len(
                entity_analytics.capabilities["options"]
            )
