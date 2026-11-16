"""Tests for the Broadlink diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from . import get_device


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    device = get_device("Guest room")
    mock_api = device.get_mock_api()
    mock_api.get_full_status.return_value = {
        "sensor": 0,
        "power": 1,
        "auto_mode": 0,
        "active": 1,
        "room_temp": 22,
        "thermostat_temp": 23,
        "external_temp": 30,
    }
    mock_setup = await device.setup_entry(hass, mock_api=mock_api)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_setup.entry)
        == snapshot
    )
