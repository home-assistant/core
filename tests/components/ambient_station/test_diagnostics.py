"""Test Ambient PWS diagnostics."""
from syrupy import SnapshotAssertion

from homeassistant.components.ambient_station import DOMAIN
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    data_station,
    setup_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    ambient = hass.data[DOMAIN][config_entry.entry_id]
    ambient.stations = data_station
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
