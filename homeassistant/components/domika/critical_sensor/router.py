"""Critical sensor router."""

from typing import Any

import voluptuous as vol

from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.core import HomeAssistant, callback

from ..const import LOGGER
from .enums import NotificationType
from .service import get


@websocket_command(
    {
        vol.Required("type"): "domika/critical_sensors",
    },
)
@callback
def websocket_domika_critical_sensors(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle domika critical sensors request."""
    msg_id: int | None = msg.get("id")
    if msg_id is None:
        LOGGER.error('Got websocket message "critical_sensors", msg_id is missing')
        return

    LOGGER.debug('Got websocket message "critical_sensors", data: %s', msg)

    sensors_data = get(hass, NotificationType.ANY)
    result = sensors_data.to_dict()

    connection.send_result(msg_id, result)
    LOGGER.debug("Critical_sensors msg_id=%s data=%s", msg_id, result)
