"""Analytics platform."""

from homeassistant.components.analytics import AnalyticsInput, AnalyticsModifications
from homeassistant.core import HomeAssistant


async def async_modify_analytics(
    hass: HomeAssistant, analytics_input: AnalyticsInput
) -> AnalyticsModifications:
    """Modify the analytics."""
    return AnalyticsModifications(remove=True)
