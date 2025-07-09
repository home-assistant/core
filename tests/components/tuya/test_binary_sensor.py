"""Test Tuya binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import DeviceListener, ManagerCompat
from homeassistant.components.tuya.const import DPCode
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import DEVICE_MOCKS, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.BINARY_SENSOR in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    [k for k, v in DEVICE_MOCKS.items() if Platform.BINARY_SENSOR not in v],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_platform_setup_no_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert not er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )


@pytest.mark.parametrize(
    ("mock_device_code", "fault_value", "expected_states"),
    [
        (  # No faults
            "cs_arete_two_12l_dehumidifier_air_purifier",
            0,
            [
                STATE_OFF,  # tankfull
                STATE_OFF,  # defrost
                STATE_OFF,  # E1
                STATE_OFF,  # E2
                STATE_OFF,  # L2
                STATE_OFF,  # L3
                STATE_OFF,  # L4
                STATE_OFF,  # wet
            ],
        ),
        (  # Fault 1 only
            "cs_arete_two_12l_dehumidifier_air_purifier",
            1,
            [
                STATE_ON,  # tankfull
                STATE_OFF,  # defrost
                STATE_OFF,  # E1
                STATE_OFF,  # E2
                STATE_OFF,  # L2
                STATE_OFF,  # L3
                STATE_OFF,  # L4
                STATE_OFF,  # wet
            ],
        ),
        (  # Fault 2 only
            "cs_arete_two_12l_dehumidifier_air_purifier",
            2,
            [
                STATE_OFF,  # tankfull
                STATE_ON,  # defrost
                STATE_OFF,  # E1
                STATE_OFF,  # E2
                STATE_OFF,  # L2
                STATE_OFF,  # L3
                STATE_OFF,  # L4
                STATE_OFF,  # wet
            ],
        ),
        (  # Fault 1 and 2
            "cs_arete_two_12l_dehumidifier_air_purifier",
            3,
            [
                STATE_ON,  # tankfull
                STATE_ON,  # defrost
                STATE_OFF,  # E1
                STATE_OFF,  # E2
                STATE_OFF,  # L2
                STATE_OFF,  # L3
                STATE_OFF,  # L4
                STATE_OFF,  # wet
            ],
        ),
        (  # Fault 3 only
            "cs_arete_two_12l_dehumidifier_air_purifier",
            4,
            [
                STATE_OFF,  # tankfull
                STATE_OFF,  # defrost
                STATE_ON,  # E1
                STATE_OFF,  # E2
                STATE_OFF,  # L2
                STATE_OFF,  # L3
                STATE_OFF,  # L4
                STATE_OFF,  # wet
            ],
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_fault_sensor_state_updates(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_listener: DeviceListener,
    fault_value: int,
    expected_states: list[str],
) -> None:
    """Test fault sensor state updates based on bitmap values."""
    # Setup
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Update fault status
    mock_device.status[DPCode.FAULT] = fault_value
    device_listener.update_device(mock_device, [DPCode.FAULT])
    await hass.async_block_till_done()

    # Verify states
    fault_sensors = [
        "binary_sensor.dehumidifier_tank_full",
        "binary_sensor.dehumidifier_defrost",
        "binary_sensor.dehumidifier_e1",
        "binary_sensor.dehumidifier_e2",
        "binary_sensor.dehumidifier_l2",
        "binary_sensor.dehumidifier_l3",
        "binary_sensor.dehumidifier_l4",
        "binary_sensor.dehumidifier_wet",
    ]

    for sensor_id, expected_state in zip(fault_sensors, expected_states, strict=True):
        state = hass.states.get(sensor_id)
        assert state is not None
        assert state.state == expected_state
