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
    assert isinstance(result["entry"], dict)
    assert result["entry"]["data"] == {"host": "192.168.1.160"}
    assert result["entry"]["unique_id"] == "1GU48T017973"

    assert isinstance(result["data"], dict)
    assert result["data"]["app"] == diagnostics_data["app"]
    assert result["data"]["apps"] == diagnostics_data["apps"]
    assert result["data"]["channel"] == diagnostics_data["channel"]
    assert result["data"]["channels"] == diagnostics_data["channels"]
    assert result["data"]["info"] == diagnostics_data["info"]
    assert result["data"]["media"] == diagnostics_data["media"]

    data_state = result["data"]["state"]
    assert isinstance(data_state, dict)
    assert data_state["available"] == diagnostics_data["state"]["available"]
    assert data_state["standby"] == diagnostics_data["state"]["standby"]
