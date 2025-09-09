"""Analytics platform."""

from homeassistant.components.analytics import DeviceAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_device_analytics(
    hass: HomeAssistant, entity_id: str, analytics: DeviceAnalytics
) -> None:
    """Modify the analytics for a device."""
    analytics.sw_version = None
