"""Tests for the Rehlko sensors."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rehlko.coordinator import SCAN_INTERVAL_MINUTES
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(name="platform_sensor", autouse=True)
async def platform_sensor_fixture():
    """Patch Rehlko to only load Sensor platform."""
    with patch("homeassistant.components.rehlko.PLATFORMS", [Platform.SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    rehlko_config_entry: MockConfigEntry,
    load_rehlko_config_entry: None,
) -> None:
    """Test the Rehlko sensors."""
    await snapshot_platform(
        hass, entity_registry, snapshot, rehlko_config_entry.entry_id
    )


async def test_sensor_availability_device_disconnect(
    hass: HomeAssistant,
    generator: dict[str, Any],
    mock_rehlko: AsyncMock,
    load_rehlko_config_entry: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Rehlko sensor availability when device is disconnected."""
    state = hass.states.get("sensor.generator_1_battery_voltage")
    assert state
    assert state.state == "13.9"

    generator["device"]["isConnected"] = False

    # Move time to next update
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.generator_1_battery_voltage")
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_sensor_availability_poll_failure(
    hass: HomeAssistant,
    mock_rehlko: AsyncMock,
    load_rehlko_config_entry: None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Rehlko sensor availability when cloud poll fails."""
    state = hass.states.get("sensor.generator_1_battery_voltage")
    assert state
    assert state.state == "13.9"

    mock_rehlko.get_generator_data.side_effect = Exception("Test exception")

    # Move time to next update
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.generator_1_battery_voltage")
    assert state
    assert state.state == STATE_UNAVAILABLE
