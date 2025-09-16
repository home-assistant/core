"""HTTP endpoints for analytics integration."""

from aiohttp import web

from homeassistant.components.http import KEY_HASS, HomeAssistantView, require_admin
from homeassistant.core import HomeAssistant

from .analytics import async_devices_payload


class AnalyticsDevicesView(HomeAssistantView):
    """View to handle analytics devices payload download requests."""

    url = "/api/analytics/devices"
    name = "api:analytics:devices"

    @require_admin
    async def get(self, request: web.Request) -> web.Response:
        """Return analytics devices payload as JSON."""
        hass: HomeAssistant = request.app[KEY_HASS]
        payload = await async_devices_payload(hass)
        return self.json(
            payload,
            headers={
                "Content-Disposition": "attachment; filename=analytics_devices.json"
            },
        )
