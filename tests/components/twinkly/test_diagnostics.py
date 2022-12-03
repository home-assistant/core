"""Tests for the diagnostics of the twinly component."""
from homeassistant.core import HomeAssistant

from . import ClientMock
from .test_light import _create_entries

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass: HomeAssistant, hass_client) -> None:
    """Test the diagnostics data."""
    client = ClientMock()
    _, _, _, config_entry = await _create_entries(hass, client)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag["entry"]["title"] == "Mock Title"
    assert diag["entry"]["data"]["host"] == "**REDACTED**"
    assert "effect_list" in diag["entry"]["attributes"]
