"""Test Airly diagnostics."""
import json

from tests.common import load_fixture
from tests.components.airly import init_integration
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, aioclient_mock, hass_client):
    """Test config entry diagnostics."""
    entry = await init_integration(hass, aioclient_mock)

    coordinator_data = json.loads(load_fixture("diagnostics_data.json", "airly"))

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["config_entry_data"] == {
        "api_key": "**REDACTED**",
        "latitude": "**REDACTED**",
        "longitude": "**REDACTED**",
        "name": "Home",
    }
    assert result["coordinator_data"] == coordinator_data
