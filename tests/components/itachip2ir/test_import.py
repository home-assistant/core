"""Tests for importing the iTach IP2IR integration."""

from homeassistant.components.itachip2ir.config_flow import Itachip2irConfigFlow
from homeassistant.config_entries import ConfigFlow


def test_config_flow_loads() -> None:
    """Ensure config flow class loads."""
    assert issubclass(Itachip2irConfigFlow, ConfigFlow)
