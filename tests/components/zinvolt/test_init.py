"""Test the Zinvolt initialization."""

from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion
from zinvolt.exceptions import ZinvoltError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


async def test_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Zinvolt device."""
    await setup_integration(hass, mock_config_entry)
    devices = device_registry.devices
    for device in devices.values():
        assert device == snapshot(name=list(device.identifiers)[0][1])


async def test_coordinator_tolerates_unit_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_zinvolt_client: AsyncMock,
) -> None:
    """A failing per-unit fetch should not take down the whole coordinator."""
    mock_zinvolt_client.get_battery_unit.side_effect = ZinvoltError(
        "The device does not exist"
    )
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
