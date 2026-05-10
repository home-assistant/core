"""Test the CatGenie sensor platform."""

from copy import deepcopy
from typing import Any, cast
from unittest.mock import MagicMock

from catgenie import Device
from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.catgenie.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_DATA

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_sensors_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that sensor entities are created for each device."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_clean_progress_unavailable_when_idle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that clean_progress sensor is unavailable when not cleaning."""
    idle_device_data = deepcopy(MOCK_DEVICE_DATA)
    operation_status = cast(dict[str, Any], idle_device_data["operationStatus"])
    operation_status["state"] = 0
    operation_status["progress"] = 0
    mock_catgenie_client.get_devices.return_value = [
        Device.model_validate(idle_device_data)
    ]

    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_sensor_device_removed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_catgenie_auth: MagicMock,
    mock_catgenie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test sensors become unavailable when device disappears from coordinator data."""
    entry = mock_config_entry
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Device disappears from the API response
    mock_catgenie_client.get_devices.return_value = []

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
