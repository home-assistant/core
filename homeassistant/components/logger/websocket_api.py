"""Websocekt API handlers for the hassio integration."""
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.core import HomeAssistant, callback
from homeassistant.loader import IntegrationNotFound, async_get_integration
from homeassistant.setup import async_get_loaded_integrations

from .const import DOMAIN, LOGSEVERITY
from .helpers import LoggerSettings


@callback
def async_load_websocket_api(hass: HomeAssistant):
    """Set up the websocket API."""
    websocket_api.async_register_command(hass, handle_integration_log_info)
    websocket_api.async_register_command(hass, handle_integration_log_level)
    websocket_api.async_register_command(hass, handle_module_log_level)


@websocket_api.websocket_command({vol.Required("type"): "logger/log_info"})
@websocket_api.async_response
async def handle_integration_log_info(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle integrations logger info."""
    connection.send_result(
        msg["id"],
        [
            {
                "domain": integration,
                "level": logging.getLogger(
                    f"homeassistant.components.{integration}"
                ).getEffectiveLevel(),
            }
            for integration in async_get_loaded_integrations(hass)
        ],
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "logger/integration_log_level",
        vol.Required("integration"): str,
        vol.Required("level"): vol.In(LOGSEVERITY),
        vol.Required("persistence"): vol.In(["none", "once", "permanent"]),
    }
)
@websocket_api.async_response
async def handle_integration_log_level(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle setting integration log level."""
    try:
        await async_get_integration(hass, msg["integration"])
    except IntegrationNotFound:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "Integration not found"
        )
        return
    settings: LoggerSettings = hass.data[DOMAIN]["settings"]
    await settings.async_update(
        hass,
        msg["integration"],
        {
            "level": msg["level"],
            "persistence": msg["persistence"],
            "type": "integration",
        },
    )
    connection.send_message(websocket_api.messages.result_message(msg["id"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "logger/log_level",
        vol.Required("module"): str,
        vol.Required("level"): vol.In(LOGSEVERITY),
        vol.Required("persistence"): vol.In(["none", "once", "permanent"]),
    }
)
@websocket_api.async_response
async def handle_module_log_level(
    hass: HomeAssistant, connection: ActiveConnection, msg: dict[str, Any]
) -> None:
    """Handle setting integration log level."""
    settings: LoggerSettings = hass.data[DOMAIN]["settings"]
    await settings.async_update(
        hass,
        msg["module"],
        {
            "level": msg["level"],
            "persistence": msg["persistence"],
            "type": "module",
        },
    )
    connection.send_message(websocket_api.messages.result_message(msg["id"]))
