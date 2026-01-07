"""Test Tuya binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_zibqa9dutqyaxym2"],
)
@pytest.mark.parametrize(
    ("fault_value", "tankfull", "defrost", "wet"),
    [
        (0, "off", "off", "off"),
        (0x1, "on", "off", "off"),
        (0x2, "off", "on", "off"),
        (0x80, "off", "off", "on"),
        (0x83, "on", "on", "on"),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_bitmap(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    fault_value: int,
    tankfull: str,
    defrost: str,
    wet: str,
) -> None:
    """Test BITMAP fault sensor on cs_zibqa9dutqyaxym2."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    assert hass.states.get("binary_sensor.dehumidifier_tank_full").state == "off"
    assert hass.states.get("binary_sensor.dehumidifier_defrost").state == "off"
    assert hass.states.get("binary_sensor.dehumidifier_wet").state == "off"

    await mock_listener.async_send_device_update(
        hass, mock_device, {"fault": fault_value}
    )

    assert hass.states.get("binary_sensor.dehumidifier_tank_full").state == tankfull
    assert hass.states.get("binary_sensor.dehumidifier_defrost").state == defrost
    assert hass.states.get("binary_sensor.dehumidifier_wet").state == wet


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_oxslv1c9"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_update_only_when_dpcode_in_updated_properties(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test binary sensor only updates when its dpcode is in updated properties.

    This test verifies that when an update event comes with properties that do NOT
    include the binary sensor's dpcode (e.g., a battery event for a door sensor),
    the binary sensor state is not changed.
    """
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state should be off (doorcontact_state is false in fixture)
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "off"
    initial_last_changed = state.last_changed

    # Manually change the device status to simulate a stale value
    # that should NOT be reflected since battery_percentage is not doorcontact_state
    mock_device.status["doorcontact_state"] = True

    # Send an update with only battery_percentage - door sensor should NOT update
    await mock_listener.async_send_device_update(
        hass, mock_device, {"battery_percentage": 80}
    )

    # State should remain "off" because doorcontact_state was not in the update
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "off"
    assert state.last_changed == initial_last_changed


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_oxslv1c9"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_update_when_dpcode_in_updated_properties(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test binary sensor updates when its dpcode is in updated properties.

    This test verifies that when an update event comes with properties that
    include the binary sensor's dpcode, the state is properly updated.
    """
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state should be off (doorcontact_state is false in fixture)
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "off"

    # Send an update with doorcontact_state - door sensor SHOULD update
    await mock_listener.async_send_device_update(
        hass, mock_device, {"doorcontact_state": True}
    )

    # State should now be "on" because doorcontact_state was in the update
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "on"


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_oxslv1c9"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR])
async def test_update_with_multiple_properties_including_dpcode(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
) -> None:
    """Test binary sensor updates when its dpcode is among multiple updated properties.

    This test verifies that when an update event comes with multiple properties
    including the binary sensor's dpcode, the state is properly updated.
    """
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state should be off
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "off"

    # Send an update with both battery_percentage and doorcontact_state
    await mock_listener.async_send_device_update(
        hass, mock_device, {"battery_percentage": 50, "doorcontact_state": True}
    )

    # State should now be "on" because doorcontact_state was in the update
    state = hass.states.get("binary_sensor.window_downstairs_door")
    assert state is not None
    assert state.state == "on"
