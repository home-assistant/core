"""Tests for the diagnostics data provided by the Roku integration."""
import json

from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics for config entry."""
    diagnostics_data = json.loads(load_fixture("roku/roku3-diagnostics-data.json"))

    result = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert isinstance(result, dict)
    assert result["config_entry"] == {"host": "192.168.1.160"}

    assert isinstance(result["coordinator"], dict)
    assert result["coordinator"]["app"] == diagnostics_data["app"]
    assert result["coordinator"]["apps"] == diagnostics_data["apps"]
    assert result["coordinator"]["channel"] == diagnostics_data["channel"]
    assert result["coordinator"]["channels"] == diagnostics_data["channels"]
    assert result["coordinator"]["info"] == diagnostics_data["info"]
    assert result["coordinator"]["media"] == diagnostics_data["media"]

    coordinator_state = result["coordinator"]["state"]
    assert isinstance(coordinator_state, dict)
    assert coordinator_state["available"] == diagnostics_data["state"]["available"]
    assert coordinator_state["standby"] == diagnostics_data["state"]["standby"]
