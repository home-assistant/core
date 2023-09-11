"""Tests for the diagnostics of the twinly component."""
from homeassistant.core import HomeAssistant

from . import ClientMock
from .test_light import _create_entries

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test the diagnostics data."""
    client = ClientMock()
    entity, _, _, config_entry = await _create_entries(hass, client)
    config_entry.unique_id = entity.unique_id

    diag = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert diag["entry"]["title"] == "Mock Title"
    assert diag["device_info"]["sw_version"] == "2.8.10"
    assert diag["entry"]["data"]["host"] == "**REDACTED**"
    assert "effect_list" in diag["attributes"]
