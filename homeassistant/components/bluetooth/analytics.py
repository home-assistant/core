"""Analytics platform."""

from homeassistant.components.analytics import DeviceAnalytics
from homeassistant.core import HomeAssistant


async def async_modify_device_analytics(
    hass: HomeAssistant, devices_analytics: dict[str, DeviceAnalytics]
) -> None:
    """Modify the analytics for devices."""
    for device_analytics in devices_analytics.values():
        device_analytics.sw_version = None
