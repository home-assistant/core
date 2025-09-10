"""Analytics platform."""

from homeassistant.components.analytics import DeviceAnalytics, EntityAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_analytics(
    hass: HomeAssistant,
    devices_analytics: dict[str, DeviceAnalytics],
    entities_analytics: dict[str, EntityAnalytics],
) -> None:
    """Modify the analytics."""
    for device_analytics in devices_analytics.values():
        device_analytics.sw_version = None
