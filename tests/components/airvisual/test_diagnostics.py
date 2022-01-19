"""Test evil genius labs diagnostics."""
import pytest

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_airvisual):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {}
