"""The template component."""

import logging

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_ID
from homeassistant.core import Event
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.setup import ATTR_COMPONENT, EVENT_COMPONENT_LOADED

from . import binary_sensor
from .common import TEMPLATE_ENTITIES

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the template platform."""
    websocket_api.async_register_command(hass, get_templates)

    async def async_component_loaded(event: Event):
        component = event.data[ATTR_COMPONENT]

        if component == binary_sensor.DOMAIN:
            await binary_sensor.async_setup_helpers(hass)

    hass.bus.async_listen(EVENT_COMPONENT_LOADED, async_component_loaded)
    return True


@websocket_api.websocket_command({"type": "template/list"})
def get_templates(
    hass: HomeAssistantType, connection: websocket_api.ActiveConnection, msg
):
    """Get list of configured template entities."""

    connection.send_result(
        msg[ATTR_ID], TEMPLATE_ENTITIES,
    )
