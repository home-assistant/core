"""Websocket API for Lovelace."""
from __future__ import annotations

from functools import wraps
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CONF_URL_PATH, DOMAIN, ConfigNotFound
from .dashboard import LovelaceStorage


def _handle_errors(func):
    """Handle error with WebSocket calls."""

    @wraps(func)
    async def send_with_error_handling(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        url_path = msg.get(CONF_URL_PATH)
        config: LovelaceStorage | None = hass.data[DOMAIN]["dashboards"].get(url_path)

        if config is None:
            connection.send_error(
                msg["id"], "config_not_found", f"Unknown config specified: {url_path}"
            )
            return

        error = None
        try:
            result = await func(hass, connection, msg, config)
        except ConfigNotFound:
            error = "config_not_found", "No config found."
        except HomeAssistantError as err:
            error = "error", str(err)

        if error is not None:
            connection.send_error(msg["id"], *error)
            return

        connection.send_result(msg["id"], result)

    return send_with_error_handling


@websocket_api.websocket_command({"type": "lovelace/resources"})
@websocket_api.async_response
async def websocket_lovelace_resources(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send Lovelace UI resources over WebSocket configuration."""
    resources = hass.data[DOMAIN]["resources"]

    if hass.config.safe_mode:
        connection.send_result(msg["id"], [])
        return

    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    connection.send_result(msg["id"], resources.async_items())


@websocket_api.websocket_command(
    {
        "type": "lovelace/config",
        vol.Optional("force", default=False): bool,
        vol.Optional(CONF_URL_PATH): vol.Any(None, cv.string),
    }
)
@websocket_api.async_response
@_handle_errors
async def websocket_lovelace_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    config: LovelaceStorage,
) -> None:
    """Send Lovelace UI config over WebSocket configuration."""
    return await config.async_load(msg["force"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "lovelace/config/save",
        "config": vol.Any(str, dict),
        vol.Optional(CONF_URL_PATH): vol.Any(None, cv.string),
    }
)
@websocket_api.async_response
@_handle_errors
async def websocket_lovelace_save_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    config: LovelaceStorage,
) -> None:
    """Save Lovelace UI configuration."""
    await config.async_save(msg["config"])


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "lovelace/config/delete",
        vol.Optional(CONF_URL_PATH): vol.Any(None, cv.string),
    }
)
@websocket_api.async_response
@_handle_errors
async def websocket_lovelace_delete_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    config: LovelaceStorage,
) -> None:
    """Delete Lovelace UI configuration."""
    await config.async_delete()


@websocket_api.websocket_command({"type": "lovelace/dashboards/list"})
@callback
def websocket_lovelace_dashboards(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete Lovelace UI configuration."""
    connection.send_result(
        msg["id"],
        [
            dashboard.config
            for dashboard in hass.data[DOMAIN]["dashboards"].values()
            if dashboard.config
        ],
    )
