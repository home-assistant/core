"""Types for the MCP server integration."""

from homeassistant.config_entries import ConfigEntry  # type: ignore[import-untyped]

from .runtime import MCPServerRuntime

MCPServerConfigEntry = ConfigEntry[MCPServerRuntime]
