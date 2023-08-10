"""Handle websocket api for S2."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection, decorators
from homeassistant.core import HomeAssistant, callback

from .helpers import S2FlexMeasuresClient, get_fm_client

# HA specific
ID = "id"
TYPE = "type"

# S2 specific
TYPE_RESULT = "ReceptionStatus"


def async_get_flexmeasures_client(func: Callable) -> Callable:
    """Decorate function to get the FlexMeasuresClient."""

    @wraps(func)
    async def _get_fm_client(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Provide the FlexMeasures client to the function."""
        fm_client = get_fm_client(hass)

        await func(hass, connection, msg, fm_client)

    return _get_fm_client


@callback
def async_register_s2_api(hass: HomeAssistant) -> None:
    """Register a single API endpoint for S2 messages."""
    websocket_api.async_register_command(hass, handle_s2_message)


@callback
@decorators.websocket_command(
    {
        vol.Required(TYPE): "S2",
        vol.Required("message_id"): str,
        vol.Required("message_type"): str,
    }
)
@websocket_api.async_response
@async_get_flexmeasures_client
async def handle_s2_message(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    coordinator: S2FlexMeasuresClient,
) -> None:
    """Handle S2 message by telling the coordinator about it."""
    coordinator.parse_message(msg)

    connection.send_message(s2_result_message(msg["id"], msg["message_id"], {}))


def s2_result_message(iden: int, message_id: str, result: Any = None) -> dict[str, Any]:
    """Return an S2 success result message.

    Based on websocket_api.messages.result_message
    # todo: discuss whether we want to keep the default HA fields
    """
    return {
        ID: iden,
        TYPE: "S2",
        "message_id": message_id,
        "message_type": TYPE_RESULT,
        "status": True,
        "diagnostic_label": result,
    }


def s2_error_message(
    iden: int | None, message_id: str | None, code: str, message: str
) -> dict[str, Any]:
    """Return an S2 error result message.

    Based on websocket_api.messages.error_message
    # todo: discuss whether we want to keep the default HA fields
    """
    return {
        ID: iden,
        TYPE: "S2",
        "message_id": message_id,
        "message_type": TYPE_RESULT,
        "status": False,
        "diagnostic_label": {"code": code, "message": message},
    }
