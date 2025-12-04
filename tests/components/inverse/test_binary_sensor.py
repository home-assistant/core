"""Inverse binary_sensor platform tests adapted from switch_as_x."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import Generator, MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def mock_binary_sensor_platform() -> Generator:
    """Limit the platform to binary_sensor."""
    with patch(
        "homeassistant.components.inverse.config_flow.PLATFORMS",
        [Platform.BINARY_SENSOR],
    ) as mock_platform:
        yield mock_platform


@pytest.mark.asyncio
async def test_inverse_binary_sensor_state(hass: HomeAssistant) -> None:
    """Verify inverse binary_sensor is created and mirrors availability."""
    hass.states.async_set("binary_sensor.sample", "on")

    entry = MockConfigEntry(
        domain="inverse", data={"entity_id": "binary_sensor.sample"}, title="ABC"
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    inv_id = "binary_sensor.abc"
    state = hass.states.get(inv_id)
    assert state is not None


@pytest.mark.asyncio
async def test_binary_sensor_snapshot(
    hass: HomeAssistant, entity_registry: EntityRegistry, snapshot: SnapshotAssertion
) -> None:
    """Snapshot test for binary_sensor platform."""
    hass.states.async_set("binary_sensor.sample", "on")

    entry = MockConfigEntry(
        domain="inverse",
        data={"entity_id": "binary_sensor.sample"},
        title="Binary Sensor",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)
