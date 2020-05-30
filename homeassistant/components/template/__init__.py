"""The template component."""

import logging

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_ID
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import binary_sensor
from .common import TEMPLATE_COMPONENTS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the template platform."""
    websocket_api.async_register_command(hass, get_templates)

    await binary_sensor.async_setup_helpers(hass)
    return True


@websocket_api.websocket_command({"type": "template/list"})
def get_templates(
    hass: HomeAssistantType, connection: websocket_api.ActiveConnection, msg
):
    """Get list of configured template entities."""

    connection.send_result(
        msg[ATTR_ID],
        [e.entity_id for component in TEMPLATE_COMPONENTS for e in component.entities],
    )
