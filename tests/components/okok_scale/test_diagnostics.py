"""Tests for the diagnostics data provided by the OKOK Scale integration."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.bluetooth import (
    inject_bluetooth_service_info_bleak,
)
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import OKOK_F0_SERVICE_INFO


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics for a config entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    inject_bluetooth_service_info_bleak(hass, OKOK_F0_SERVICE_INFO)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    ) == snapshot(exclude=props("created_at", "modified_at", "entry_id", "time"))
