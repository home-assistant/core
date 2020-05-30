"""The template component."""

import logging
from typing import List

from homeassistant.components import websocket_api
from homeassistant.const import ATTR_ID
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType, HomeAssistantType

from . import binary_sensor

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the template platform."""
    websocket_api.async_register_command(hass, get_templates)

    await binary_sensor.async_setup_helpers(hass, register_component)
    return True


@websocket_api.websocket_command({"type": "template/list"})
def get_templates(
    hass: HomeAssistantType, connection: websocket_api.ActiveConnection, msg
):
    """Get list of configured template entities."""

    connection.send_result(
        msg[ATTR_ID],
        [e.entity_id for component in template_components for e in component.entities],
    )


template_components: List[EntityComponent] = []


def register_component(component: EntityComponent):
    """Register an template EntityComponent."""
    template_components.append(component)
