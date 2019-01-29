"""System health component."""
from collections import OrderedDict
from typing import Callable, Dict

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.loader import bind_hass
from homeassistant.helpers.typing import HomeAssistantType, ConfigType
from homeassistant.components import websocket_api

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
    hass.components.websocket_api.async_register_command(handle_info)
    return True


@websocket_api.async_response
@websocket_api.websocket_command({
    vol.Required('type'): 'system_health/info'
})
async def handle_info(hass: HomeAssistantType,
                      connection: websocket_api.ActiveConnection,
                      msg: Dict):
    """Handle an info request."""
    info_callbacks = hass.data.get(DOMAIN, {}).get('info', {})
    data = OrderedDict()
    data['homeassistant'] = \
        await hass.helpers.system_info.async_get_system_info()

    for domain, info_callback in info_callbacks.items():
        data[domain] = info_callback(hass)

    connection.send_message(websocket_api.result_message(msg['id'], data))
