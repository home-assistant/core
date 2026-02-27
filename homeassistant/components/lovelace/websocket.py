"""Websocket API for Lovelace."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.components import ai_task, websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.json import json_fragment
from homeassistant.util.json import json_loads

from .const import (
    CONF_RESOURCE_MODE,
    CONF_URL_PATH,
    DOMAIN,
    LOVELACE_DATA,
    ConfigNotFound,
)
from .dashboard import LovelaceConfig
from .llm import LovelaceDashboardGenerationAPI, build_generation_instructions

if TYPE_CHECKING:
    from .resources import ResourceStorageCollection

type AsyncLovelaceWebSocketCommandHandler[_R] = Callable[
    [HomeAssistant, websocket_api.ActiveConnection, dict[str, Any], LovelaceConfig],
    Awaitable[_R],
]


def _handle_errors[_R](
    func: AsyncLovelaceWebSocketCommandHandler[_R],
) -> websocket_api.AsyncWebSocketCommandHandler:
    """Handle error with WebSocket calls."""

    @wraps(func)
    async def send_with_error_handling(
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        url_path = msg.get(CONF_URL_PATH)

        # When url_path is None, prefer "lovelace" dashboard if it exists (for YAML mode)
        # Otherwise fall back to dashboards[None] (storage mode default)
        if url_path is None:
            config = hass.data[LOVELACE_DATA].dashboards.get(DOMAIN) or hass.data[
                LOVELACE_DATA
            ].dashboards.get(None)
        else:
            config = hass.data[LOVELACE_DATA].dashboards.get(url_path)

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


@websocket_api.async_response
async def websocket_lovelace_resources(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send Lovelace UI resources over WebSocket connection.

    This function is used in YAML mode.
    """
    await websocket_lovelace_resources_impl(hass, connection, msg)


async def websocket_lovelace_resources_impl(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Help send Lovelace UI resources over WebSocket connection.

    This function is called by both Storage and YAML mode WS handlers.
    """
    resources = hass.data[LOVELACE_DATA].resources
    if TYPE_CHECKING:
        assert isinstance(resources, ResourceStorageCollection)

    if hass.config.safe_mode:
        connection.send_result(msg["id"], [])
        return

    if not resources.loaded:
        await resources.async_load()
        resources.loaded = True

    connection.send_result(msg["id"], resources.async_items())


@websocket_api.websocket_command({"type": "lovelace/info"})
@websocket_api.async_response
async def websocket_lovelace_info(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send Lovelace UI info over WebSocket connection."""
    connection.send_result(
        msg["id"],
        {CONF_RESOURCE_MODE: hass.data[LOVELACE_DATA].resource_mode},
    )


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
    config: LovelaceConfig,
) -> json_fragment:
    """Send Lovelace UI config over WebSocket connection."""
    return await config.async_json(msg["force"])


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
    config: LovelaceConfig,
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
    config: LovelaceConfig,
) -> None:
    """Delete Lovelace UI configuration."""
    await config.async_delete()


def _coerce_generated_dashboard(data: Any) -> dict[str, Any]:
    """Coerce AI output into a dashboard config object."""
    if isinstance(data, dict):
        return data

    if not isinstance(data, str):
        raise HomeAssistantError("Generated dashboard must be a valid JSON object")

    candidates = [data.strip()]

    if "```" in data:
        for block in data.split("```"):
            candidate = block.strip()
            if not candidate:
                continue
            if candidate.casefold().startswith("json"):
                candidate = candidate[4:].strip()
            candidates.append(candidate)

    for candidate in candidates:
        try:
            parsed = json_loads(candidate)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            return parsed

    raise HomeAssistantError("Generated dashboard must be a valid JSON object")


def _validate_generated_dashboard(data: Any) -> dict[str, Any]:
    """Validate generated dashboard response."""
    if not isinstance(data, dict):
        raise HomeAssistantError("Generated dashboard must be an object")

    views = data.get("views")
    if not isinstance(views, list) or not views:
        raise HomeAssistantError(
            "Generated dashboard must include at least one view in `views`"
        )

    if not all(isinstance(view, dict) for view in views):
        raise HomeAssistantError("Each dashboard view must be an object")

    return data


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        "type": "lovelace/config/generate",
        vol.Required("prompt"): cv.string,
    }
)
@websocket_api.async_response
async def websocket_lovelace_generate_dashboard(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Generate a Lovelace dashboard configuration from a prompt."""
    if ai_task.DOMAIN not in hass.config.components:
        connection.send_error(
            msg["id"],
            "error",
            "AI Task integration is not available. Configure AI Task first.",
        )
        return

    try:
        result = await ai_task.async_generate_data(
            hass,
            task_name="lovelace_dashboard_generation",
            instructions=await build_generation_instructions(hass, msg["prompt"]),
            llm_api=LovelaceDashboardGenerationAPI(hass),
        )
        config = _validate_generated_dashboard(_coerce_generated_dashboard(result.data))
    except HomeAssistantError as err:
        connection.send_error(msg["id"], "error", str(err))
        return

    connection.send_result(
        msg["id"],
        {
            "conversation_id": result.conversation_id,
            "config": config,
        },
    )
