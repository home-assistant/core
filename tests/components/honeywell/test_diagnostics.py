"""Test Honeywell diagnostics."""

from unittest.mock import MagicMock

from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

YAML_CONFIG = {"username": "test-user", "password": "test-password"}


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    config_entry: MockConfigEntry,
    location: MagicMock,
    another_device: MagicMock,
) -> None:
    """Test config entry diagnostics for Honeywell."""

    location.devices_by_id[another_device.deviceid] = another_device
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids_count() == 8

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
