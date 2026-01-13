"""Tests for the Tibber binary sensors."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.recorder import Recorder
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import create_tibber_device

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.BINARY_SENSOR]


async def test_binary_sensor_snapshot(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test binary sensor entities against snapshot."""
    device = create_tibber_device(
        connector_status="connected",
        charging_status="charging",
        device_status="on",
    )
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    (
        "entity_suffix",
        "connector_status",
        "charging_status",
        "device_status",
        "expected_state",
    ),
    [
        ("plug", "connected", None, None, STATE_ON),
        ("plug", "disconnected", None, None, STATE_OFF),
        ("charging", None, "charging", None, STATE_ON),
        ("charging", None, "idle", None, STATE_OFF),
        ("power", None, None, "on", STATE_ON),
        ("power", None, None, "off", STATE_OFF),
    ],
)
async def test_binary_sensor_states(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: AsyncMock,
    setup_credentials: None,
    entity_suffix: str,
    connector_status: str | None,
    charging_status: str | None,
    device_status: str | None,
    expected_state: str,
) -> None:
    """Test binary sensor state values."""
    device = create_tibber_device(
        connector_status=connector_status,
        charging_status=charging_status,
        device_status=device_status,
    )
    data_api_client_mock.get_all_devices = AsyncMock(return_value={"device-id": device})
    data_api_client_mock.update_devices = AsyncMock(return_value={"device-id": device})

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"binary_sensor.test_device_{entity_suffix}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == expected_state
