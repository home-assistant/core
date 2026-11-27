"""Tests for the Tile BLE diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import inject_bluetooth_service_info
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import TILE_SERVICE_INFO, setup_integration


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics of a Tile in range."""
    await setup_integration(hass, mock_config_entry)
    inject_bluetooth_service_info(hass, TILE_SERVICE_INFO)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("time"))


async def test_diagnostics_out_of_range(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics of a Tile that has not been seen."""
    await setup_integration(hass, mock_config_entry)

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)
        == snapshot
    )
