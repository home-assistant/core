"""Types for the MCP server integration."""

from homeassistant.config_entries import ConfigEntry

from .runtime import MCPServerRuntime

MCPServerConfigEntry = ConfigEntry[MCPServerRuntime]
