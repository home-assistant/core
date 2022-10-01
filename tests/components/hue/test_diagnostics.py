"""Test Hue diagnostics."""

from .conftest import setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics_v1(hass, hass_client, mock_bridge_v1):
    """Test diagnostics v1."""
    await setup_platform(hass, mock_bridge_v1, [])
    config_entry = hass.config_entries.async_entries("hue")[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == {}


async def test_diagnostics_v2(hass, hass_client, mock_bridge_v2):
    """Test diagnostics v2."""
    mock_bridge_v2.api.get_diagnostics.return_value = {"hello": "world"}
    await setup_platform(hass, mock_bridge_v2, [])
    config_entry = hass.config_entries.async_entries("hue")[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == {"hello": "world"}
