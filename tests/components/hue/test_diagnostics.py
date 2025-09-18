"""Test Hue diagnostics."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from homeassistant.util.json import JsonArrayType

from .conftest import setup_platform

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics_v1(
    hass: HomeAssistant, hass_client: ClientSessionGenerator, mock_bridge_v1: Mock
) -> None:
    """Test diagnostics v1."""
    await setup_platform(hass, mock_bridge_v1, [])
    config_entry = hass.config_entries.async_entries("hue")[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == {}


async def test_diagnostics_v2(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_bridge_v2: Mock,
    v2_resources_test_data: JsonArrayType,
) -> None:
    """Test diagnostics v2."""
    await mock_bridge_v2.api.load_test_data(v2_resources_test_data)
    mock_bridge_v2.api.get_diagnostics.return_value = {"hello": "world"}
    await setup_platform(hass, mock_bridge_v2, [])
    config_entry = hass.config_entries.async_entries("hue")[0]
    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == {"hello": "world"}
