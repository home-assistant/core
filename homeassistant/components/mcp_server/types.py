"""Types for the MCP server integration."""

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry

from .session import SessionManager

type MCPServerConfigEntry = ConfigEntry[SessionManager]


@dataclass(frozen=True, slots=True)
class MCPRequestContext:
    """Transport context for a single MCP request."""

    device_id: str | None
