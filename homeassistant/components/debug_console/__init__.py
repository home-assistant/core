"""The Debug console integration, running Python inside Home Assistant."""

import asyncio

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .safeguards import async_setup_safeguards
from .session import (
    DATA_LLM_SESSIONS,
    DATA_MCP_SESSIONS,
    DATA_SESSIONS,
    async_close_sessions,
)
from .websocket_api import async_register_websocket_commands

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Debug console.

    Only from YAML, on every version, which a browser cannot add: code in the
    browser of an administrator, like a custom card, could otherwise enable
    the console and run code unnoticed.
    """
    sessions = hass.data[DATA_SESSIONS] = {}
    mcp_sessions = hass.data[DATA_MCP_SESSIONS] = {}
    llm_sessions = hass.data[DATA_LLM_SESSIONS] = {}
    await async_setup_safeguards(hass)

    # Integrations are not unloaded on shutdown, but code still running in the
    # console should stop then too.
    async def _async_close_sessions(_event: Event) -> None:
        await asyncio.gather(
            async_close_sessions(sessions),
            async_close_sessions(mcp_sessions),
            async_close_sessions(llm_sessions),
        )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_close_sessions)
    async_register_websocket_commands(hass)
    return True
