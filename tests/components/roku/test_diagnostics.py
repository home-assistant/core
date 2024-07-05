"""Tests for the diagnostics data provided by the Roku integration."""

from rokuecp import Device as RokuDevice
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_device: RokuDevice,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for config entry."""
    mock_device.state.at = dt_util.parse_datetime("2023-08-15 17:00:00-00:00")

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == snapshot
    )
