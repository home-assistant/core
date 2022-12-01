"""Handle websocket api for Matter."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from matter_server.client.exceptions import FailedCommand
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ActiveConnection
from homeassistant.core import HomeAssistant, callback

from .adapter import MatterAdapter
from .const import DOMAIN

ID = "id"
TYPE = "type"


@callback
def async_register_api(hass: HomeAssistant) -> None:
    """Register all of our api endpoints."""
    websocket_api.async_register_command(hass, websocket_commission)
    websocket_api.async_register_command(hass, websocket_commission_on_network)
    websocket_api.async_register_command(hass, websocket_set_thread_dataset)
    websocket_api.async_register_command(hass, websocket_set_wifi_credentials)


def async_get_matter_adapter(func: Callable) -> Callable:
    """Decorate function to get the MatterAdapter."""

    @wraps(func)
    async def _get_matter(
        hass: HomeAssistant, connection: ActiveConnection, msg: dict
    ) -> None:
        """Provide the Matter client to the function."""
        matter: MatterAdapter = next(iter(hass.data[DOMAIN].values()))

        await func(hass, connection, msg, matter)

    return _get_matter


def async_handle_failed_command(func: Callable) -> Callable:
    """Decorate function to handle FailedCommand and send relevant error."""

    @wraps(func)
    async def async_handle_failed_command_func(
        hass: HomeAssistant,
        connection: ActiveConnection,
        msg: dict[str, Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Handle FailedCommand within function and send relevant error."""
        try:
            await func(hass, connection, msg, *args, **kwargs)
        except FailedCommand as err:
            connection.send_error(msg[ID], err.error_code, err.args[0])

    return async_handle_failed_command_func


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/commission",
        vol.Required("code"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_commission(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Add a device to the network and commission the device."""
    await matter.matter_client.commission_with_code(msg["code"])
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/commission_on_network",
        vol.Required("pin"): int,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_commission_on_network(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Commission a device already on the network."""
    await matter.matter_client.commission_on_network(msg["pin"])
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/set_thread",
        vol.Required("thread_operation_dataset"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_set_thread_dataset(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Set thread dataset."""
    await matter.matter_client.set_thread_operational_dataset(
        msg["thread_operation_dataset"]
    )
    connection.send_result(msg[ID])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required(TYPE): "matter/set_wifi_credentials",
        vol.Required("network_name"): str,
        vol.Required("password"): str,
    }
)
@websocket_api.async_response
@async_handle_failed_command
@async_get_matter_adapter
async def websocket_set_wifi_credentials(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
    matter: MatterAdapter,
) -> None:
    """Set WiFi credentials for a device."""
    await matter.matter_client.set_wifi_credentials(
        ssid=msg["network_name"], credentials=msg["password"]
    )
    connection.send_result(msg[ID])
