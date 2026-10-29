"""Diagnostics support for the Model Context Protocol Server."""

from typing import Any

from mcp import types
from mcp.server.streamable_http import DEFAULT_NEGOTIATED_VERSION

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import llm

from .const import CONF_READ_ONLY, DOMAIN
from .http import _entry_llm_api_ids
from .server import async_get_api_instance
from .types import MCPServerConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MCPServerConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    llm_api_ids = _entry_llm_api_ids(hass, entry)
    # Diagnostics are admin only, so list the tools of APIs requiring admin too.
    owner = await hass.auth.async_get_owner()
    llm_context = llm.LLMContext(
        platform=DOMAIN,
        context=Context(user_id=owner.id) if owner else None,
        language="*",
        assistant=conversation.DOMAIN,
        device_id=None,
    )
    llm_api: dict[str, Any]
    try:
        api_instance = await async_get_api_instance(
            hass, llm_api_ids, llm_context, entry.data[CONF_READ_ONLY]
        )
    # Merged APIs raise ValueError on tool name collisions.
    except (HomeAssistantError, ValueError) as err:
        llm_api = {"error": str(err)}
    else:
        llm_api = {
            "id": api_instance.api.id,
            "name": api_instance.api.name,
            "tools": [tool.name for tool in api_instance.tools],
        }
    return {
        "config_entry_data": dict(entry.data),
        "served_llm_api_ids": llm_api_ids,
        "llm_api": llm_api,
        "available_llm_apis": [
            {"id": api.id, "name": api.name, "requires_admin": api.requires_admin}
            for api in llm.async_get_apis(hass)
        ],
        "latest_protocol_version": types.LATEST_PROTOCOL_VERSION,
        "default_negotiated_protocol_version": DEFAULT_NEGOTIATED_VERSION,
        "active_sse_sessions": entry.runtime_data.session_count,
    }
