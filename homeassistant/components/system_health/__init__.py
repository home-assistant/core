"""System health component."""
from collections import OrderedDict
from typing import Callable, Dict
from aiohttp.web import Request, Response, json_response

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components.http.view import HomeAssistantView

DEPENDENCIES = ['http']
DOMAIN = 'system_health'


@bind_hass
@callback
def async_register_info(hass: HomeAssistantType, domain: str,
                        info_callback: Callable[[HomeAssistantType], Dict]):
    """Register an info callback."""
    data = hass.data.setdefault(
        DOMAIN, OrderedDict()).setdefault('info', OrderedDict())
    data[domain] = info_callback


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the System Health component."""
    hass.http.register_view(InfoView)
    return True


class InfoView(HomeAssistantView):
    """HTTP endpoint to offer health info."""

    url = "/api/system_health/info"
    name = "api:system_health:info"

    async def get(self, request: Request) -> Response:
        """Handle GET request."""
        hass = request.app['hass']  # type: HomeAssistantType
        info_callbacks = hass.data.get(DOMAIN, {}).get('info', {})
        data = OrderedDict()
        data['homeassistant'] = \
            await hass.helpers.system_info.async_get_system_info(hass)

        for domain, info_callback in info_callbacks.items():
            data[domain] = info_callback(hass)

        return json_response(data)
