"""Support for System health ."""
import asyncio
from collections import OrderedDict
import logging
from typing import Callable, Dict

import async_timeout
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import callback
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'system_health'

INFO_CALLBACK_TIMEOUT = 5


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


async def _info_wrapper(hass, info_callback):
    """Wrap info callback."""
    try:
        with async_timeout.timeout(INFO_CALLBACK_TIMEOUT):
            return await info_callback(hass)
    except asyncio.TimeoutError:
        return {
            'error': 'Fetching info timed out'
        }
    except Exception as err:  # pylint: disable=W0703
        _LOGGER.exception("Error fetching info")
        return {
            'error': str(err)
        }


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

    if info_callbacks:
        for domain, domain_data in zip(info_callbacks, await asyncio.gather(*[
                _info_wrapper(hass, info_callback) for info_callback
                in info_callbacks.values()
        ])):
            data[domain] = domain_data

    connection.send_message(websocket_api.result_message(msg['id'], data))
