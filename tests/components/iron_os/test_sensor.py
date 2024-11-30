"""Tests for the Pinecil Sensors."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from pynecil import CommunicationError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.iron_os.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
async def sensor_only() -> AsyncGenerator[None]:
    """Enable only the sensor platform."""
    with patch(
        "homeassistant.components.iron_os.PLATFORMS",
        [Platform.SENSOR],
    ):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_pynecil: AsyncMock,
    ble_device: MagicMock,
) -> None:
    """Test the Pinecil sensor platform."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors_unavailable(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_pynecil: AsyncMock,
    ble_device: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the sensors when device disconnects."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    mock_pynecil.get_live_data.side_effect = CommunicationError
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id).state == STATE_UNAVAILABLE
