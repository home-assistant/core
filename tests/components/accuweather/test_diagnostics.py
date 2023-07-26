"""Test AccuWeather diagnostics."""

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass)

    coordinator_data = load_json_object_fixture(
        "current_conditions_data.json", "accuweather"
    )

    coordinator_data["forecast"] = []

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["config_entry_data"] == {
        "api_key": "**REDACTED**",
        "latitude": "**REDACTED**",
        "longitude": "**REDACTED**",
        "name": "Home",
    }
    assert result["coordinator_data"] == coordinator_data
