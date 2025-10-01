"""The Model Context Protocol Server integration."""

from __future__ import annotations

import logging

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers import llm

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from . import http
from .auth import async_resolve_auth_config
from .const import DOMAIN
from .event_store import InMemoryEventStore
from .runtime import MCPServerRuntime, StreamableHTTPManagerRunner
from .server import create_server
from .session import SessionManager

_LOGGER = logging.getLogger(__name__)

__all__ = [
    "CONFIG_SCHEMA",
    "DOMAIN",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:  # type: ignore[no-untyped-def]
    """Set up the Model Context Protocol component."""

    http.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Model Context Protocol Server from a config entry."""

    session_manager = SessionManager()

    llm_context = llm.LLMContext(
        platform=DOMAIN,
        context=None,
        language="*",
        assistant=conversation.DOMAIN,
        device_id=None,
    )

    llm_api_id: str | list[str] = entry.data[CONF_LLM_HASS_API]
    auth_config = await async_resolve_auth_config(hass)
    fast_server = await create_server(
        hass,
        llm_api_id,
        llm_context,
        auth_settings=auth_config.settings,
        token_verifier=auth_config.token_verifier,
    )

    event_store = InMemoryEventStore()
    streamable_manager = StreamableHTTPSessionManager(
        app=fast_server._mcp_server,  # noqa: SLF001
        event_store=event_store,
        json_response=fast_server.settings.json_response,
        stateless=fast_server.settings.stateless_http,
        security_settings=fast_server.settings.transport_security,
    )
    runner = StreamableHTTPManagerRunner(streamable_manager)

    try:
        await runner.start()
    except Exception:  # pragma: no cover - defensive
        _LOGGER.exception("Failed to start StreamableHTTP session manager")
        session_manager.close()
        raise

    entry.runtime_data = MCPServerRuntime(
        session_manager=session_manager,
        fast_server=fast_server,
        streamable_manager=streamable_manager,
        streamable_runner=runner,
        event_store=event_store,
        auth_settings=auth_config.settings,
        token_verifier=auth_config.token_verifier,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    runtime: MCPServerRuntime | None = entry.runtime_data
    if runtime is not None:
        runtime.session_manager.close()
        await runtime.streamable_runner.stop()
        entry.runtime_data = None  # type: ignore[assignment]

    return True
