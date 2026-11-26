"""Test the saj sensor platform."""

from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_fire_time_changed,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.saj.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.SENSOR]


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_aiosaj_saj")
async def test_sensors(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the sensor entities."""
    await setup_integration(hass, mock_config_entry)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_sensor_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aiosaj_saj: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sensors become unavailable when an update fails."""
    entry = await setup_integration(hass, mock_config_entry)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("sensor.saj_current_power")
    assert state is not None
    assert state.state == "5000.0"

    mock_aiosaj_saj.read = AsyncMock(return_value=False)
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.saj_current_power")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_aiosaj_saj")
async def test_sensor_without_unit_mapping_is_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aiosaj_sensors: list[MagicMock],
) -> None:
    """A channel with a unit the integration does not map gets no entity."""
    sensor = MagicMock()
    sensor.name = "pv1_voltage"
    sensor.key = "PV1vol"
    sensor.value = 350.0
    sensor.unit = "V"
    sensor.enabled = True
    mock_aiosaj_sensors.append(sensor)

    entry = await setup_integration(hass, mock_config_entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.saj_current_power") is not None
    assert hass.states.get("sensor.saj_pv1_voltage") is None
