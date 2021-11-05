"""Provide a mock config flow for the test integration."""
from homeassistant.config_entries import ConfigFlow


class TestConfigFlow(ConfigFlow, domain="test"):
    """Handle a config flow for test."""
