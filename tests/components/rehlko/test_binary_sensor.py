"""Tests for the Rehlko binary sensors."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rehlko.const import GENERATOR_DATA_DEVICE
from homeassistant.components.rehlko.coordinator import SCAN_INTERVAL_MINUTES
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(name="platform_binary_sensor", autouse=True)
async def platform_binary_sensor_fixture():
    """Patch Rehlko to only load binary_sensor platform."""
    with patch("homeassistant.components.rehlko.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    rehlko_config_entry: MockConfigEntry,
    load_rehlko_config_entry: None,
) -> None:
    """Test the Rehlko binary sensors."""
    await snapshot_platform(
        hass, entity_registry, snapshot, rehlko_config_entry.entry_id
    )


async def test_binary_sensor_states(
    hass: HomeAssistant,
    generator: dict[str, Any],
    mock_rehlko: AsyncMock,
    load_rehlko_config_entry: None,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the Rehlko binary sensor state logic."""
    assert generator["engineOilPressureOk"] is True
    state = hass.states.get("binary_sensor.generator_1_oil_pressure")
    assert state.state == STATE_OFF

    generator["engineOilPressureOk"] = False
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.generator_1_oil_pressure")
    assert state.state == STATE_ON

    generator["engineOilPressureOk"] = "Unknown State"
    with caplog.at_level(logging.WARNING):
        caplog.clear()
        freezer.tick(SCAN_INTERVAL_MINUTES)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.generator_1_oil_pressure")
    assert state.state == STATE_UNKNOWN
    assert "Unknown State" in caplog.text
    assert "engineOilPressureOk" in caplog.text


async def test_binary_sensor_connectivity_availability(
    hass: HomeAssistant,
    generator: dict[str, Any],
    mock_rehlko: AsyncMock,
    load_rehlko_config_entry: None,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the connectivity entity availability when device is disconnected."""
    state = hass.states.get("binary_sensor.generator_1_connectivity")
    assert state.state == STATE_ON

    # Entity should be available when device is disconnected
    generator[GENERATOR_DATA_DEVICE]["isConnected"] = False
    freezer.tick(SCAN_INTERVAL_MINUTES)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.generator_1_connectivity")
    assert state.state == STATE_OFF
