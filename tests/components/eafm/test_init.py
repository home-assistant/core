"""Tests for initialization."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.eafm.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_get_station")
async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test being able to load and unload an entry."""
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    assert (
        dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
        == snapshot
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_get_station")
async def test_update_device_identifiers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test being able to update device identifiers."""
    device_entry = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "measure-id", "L1234")},
    )

    entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    device_entry = entries[0]
    assert (DOMAIN, "measure-id", "L1234") in device_entry.identifiers
    assert (DOMAIN, "L1234") not in device_entry.identifiers

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    await hass.async_block_till_done()

    entries = dr.async_entries_for_config_entry(
        device_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 1
    device_entry = entries[0]
    assert (DOMAIN, "measure-id", "L1234") not in device_entry.identifiers
    assert (DOMAIN, "L1234") in device_entry.identifiers
