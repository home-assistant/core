"""Test Tuya binary sensor."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice

from homeassistant.components.tuya import DeviceListener, ManagerCompat
from homeassistant.components.tuya.const import (
    CONF_ENDPOINT,
    CONF_TERMINAL_ID,
    CONF_TOKEN_INFO,
    CONF_USER_CODE,
    DOMAIN,
    DPCode,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture
def mock_manager() -> ManagerCompat:
    """Mock Tuya Manager."""
    manager = MagicMock(spec=ManagerCompat)
    manager.device_map = {}
    manager.mq = MagicMock()
    return manager


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        title="Test Tuya Device",
        domain=DOMAIN,
        data={
            CONF_USER_CODE: "test_user",
            CONF_TERMINAL_ID: "test_terminal",
            CONF_ENDPOINT: "test_endpoint",
            CONF_TOKEN_INFO: "test_token",
        },
        unique_id="test_unique_id",
    )


@pytest.fixture
def device_listener(hass: HomeAssistant, mock_manager: ManagerCompat) -> DeviceListener:
    """Create a DeviceListener for testing."""
    listener = DeviceListener(hass, mock_manager)
    mock_manager.add_device_listener(listener)
    return listener


async def test_fault_sensor_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device_arete_two_12l_dehumidifier_air_purifier: CustomerDevice,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test fault sensor entity discovery and setup."""
    # Setup
    mock_manager.device_map = {
        mock_device_arete_two_12l_dehumidifier_air_purifier.id: mock_device_arete_two_12l_dehumidifier_air_purifier,
    }
    mock_config_entry.add_to_hass(hass)

    # Initialize the component
    with (
        patch("homeassistant.components.tuya.ManagerCompat", return_value=mock_manager),
        patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR]),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("fault_value", "expected_states"),
    [
        (  # No faults
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
async def test_fault_sensor_state_updates(
    hass: HomeAssistant,
    mock_manager: ManagerCompat,
    mock_config_entry: MockConfigEntry,
    mock_device_arete_two_12l_dehumidifier_air_purifier: CustomerDevice,
    device_listener: DeviceListener,
    fault_value: int,
    expected_states: list[str],
) -> None:
    """Test fault sensor state updates based on bitmap values."""
    # Setup
    mock_manager.device_map = {
        mock_device_arete_two_12l_dehumidifier_air_purifier.id: mock_device_arete_two_12l_dehumidifier_air_purifier
    }
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.tuya.ManagerCompat", return_value=mock_manager
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Update fault status
    mock_device_arete_two_12l_dehumidifier_air_purifier.status[DPCode.FAULT] = (
        fault_value
    )
    device_listener.update_device(
        mock_device_arete_two_12l_dehumidifier_air_purifier, [DPCode.FAULT]
    )
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
