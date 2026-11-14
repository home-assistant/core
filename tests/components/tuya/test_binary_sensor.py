"""Test Tuya binary sensor platform."""

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "no_quirk")
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
    ["mcs_oxslv1c9"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays
        # at available_reported
        ({"battery_percentage": 80}, "off", "2024-01-01T00:00:20+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"doorcontact_state": True}, "on", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"battery_percentage": 50, "doorcontact_state": True},
            "on",
            "2024-01-01T00:01:00+00:00",
        ),
    ],
)
@pytest.mark.freeze_time("2024-01-01")
async def test_selective_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    freezer: FrozenDateTimeFactory,
    updates: dict[str, Any],
    expected_state: str,
    last_reported: str,
) -> None:
    """Test skip_update/last_reported."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    await check_selective_state_update(
        hass,
        mock_device,
        notification_helper,
        freezer,
        entity_id="binary_sensor.window_downstairs_door",
        dpcode="doorcontact_state",
        initial_state="off",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


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
async def test_bitmap(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
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

    await notification_helper.async_send_device_update(
        mock_device, {"fault": fault_value}
    )

    assert hass.states.get("binary_sensor.dehumidifier_tank_full").state == tankfull
    assert hass.states.get("binary_sensor.dehumidifier_defrost").state == defrost
    assert hass.states.get("binary_sensor.dehumidifier_wet").state == wet


@pytest.mark.parametrize(
    "mock_device_code",
    ["hps_gyrbdy2q"],
)
@pytest.mark.parametrize(
    ("drop_value", "expected_state"),
    [("normal", "off"), ("drop", "on")],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default", "no_quirk")
async def test_drop_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    drop_value: str,
    expected_state: str,
) -> None:
    """Test drop_state transitions: normal -> off, drop -> on."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    entity_id = "binary_sensor.60gren_ti_die_dao_zigbee_fall"
    assert hass.states.get(entity_id).state == "off"

    await notification_helper.async_send_device_update(
        mock_device, {"drop_state": drop_value}
    )

    assert hass.states.get(entity_id).state == expected_state


@pytest.mark.parametrize("mock_device_code", ["sp_8zrzjldq07tlxnlv"])
@pytest.mark.parametrize(
    ("dpcode", "entity_id"),
    [
        ("feed_block_status", "binary_sensor.8zrzjldq07tlxnlv_feed_blocked"),
        ("feed_stuck_status", "binary_sensor.8zrzjldq07tlxnlv_food_stuck"),
    ],
)
async def test_camera_pet_feeder(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
    dpcode: str,
    entity_id: str,
) -> None:
    """Test pet feeder problem sensors on a camera (sp) device."""
    # The feeder datapoints are only provided by a quirk
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    assert dpcode in mock_device.status_range

    assert hass.states.get(entity_id).state == "off"

    await notification_helper.async_send_device_update(mock_device, {dpcode: True})

    assert hass.states.get(entity_id).state == "on"
