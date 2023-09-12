"""Test AccuWeather diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import init_integration

from tests.common import load_json_object_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = await init_integration(hass)

    coordinator_data = load_json_object_fixture(
        "current_conditions_data.json", "accuweather"
    )

    coordinator_data["forecast"] = []

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
