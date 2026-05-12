"""Test Tuya binary sensor platform."""

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.BINARY_SENSOR]):
        yield


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
    ["cs_u0wirz487erb0eka"],
)
@pytest.mark.parametrize(
    ("fault_value", "tankfull", "cleaning", "e1", "cl", "ch", "lo", "coil", "motor"),
    [
        (0, "off", "off", "off", "off", "off", "off", "off", "off"),
        (0x1, "on", "off", "off", "off", "off", "off", "off", "off"),
        (0x2, "off", "on", "off", "off", "off", "off", "off", "off"),
        (0x4, "off", "off", "on", "off", "off", "off", "off", "off"),
        (0x8, "off", "off", "off", "on", "off", "off", "off", "off"),
        (0x10, "off", "off", "off", "off", "on", "off", "off", "off"),
        (0x20, "off", "off", "off", "off", "off", "on", "off", "off"),
        (0x40, "off", "off", "off", "off", "off", "off", "on", "off"),
        (0x80, "off", "off", "off", "off", "off", "off", "off", "on"),
        (0xFF, "on", "on", "on", "on", "on", "on", "on", "on"),
    ],
)
@pytest.mark.parametrize(
    "mock_device_code",
    ["cs_u0wirz487erb0eka"],
)
@pytest.mark.parametrize(
    (
        "bitmap_val",
        "expected_full",
        "expected_cleaning",
        "expected_e1",
        "expected_cl",
        "expected_ch",
        "expected_lo",
        "expected_coil",
        "expected_motor",
    ),
    [
        (0, "off", "off", "off", "off", "off", "off", "off", "off"),
        (1, "on", "off", "off", "off", "off", "off", "off", "off"),
        (2, "off", "on", "off", "off", "off", "off", "off", "off"),
        (4, "off", "off", "on", "off", "off", "off", "off", "off"),
        (8, "off", "off", "off", "on", "off", "off", "off", "off"),
        (16, "off", "off", "off", "off", "on", "off", "off", "off"),
        (32, "off", "off", "off", "off", "off", "on", "off", "off"),
        (64, "off", "off", "off", "off", "off", "off", "on", "off"),
        (128, "off", "off", "off", "off", "off", "off", "off", "on"),
        (255, "on", "on", "on", "on", "on", "on", "on", "on"),
    ],
)
async def test_bitmap_probreeze(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_registry: er.EntityRegistry,
    bitmap_val: int,
    expected_full: str,
    expected_cleaning: str,
    expected_e1: str,
    expected_cl: str,
    expected_ch: str,
    expected_lo: str,
    expected_coil: str,
    expected_motor: str,
) -> None:
    """Test fault bitmap for Pro Breeze OmniDry."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    mock_device.status = {DPCode.FAULT: bitmap_val}
    for listener in mock_manager.device_listeners:
        listener.update_device(mock_device, [DPCode.FAULT], None)
    await hass.async_block_till_done()

    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_tank_full"
        ).state
        == expected_full
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_filter_cleaning"
        ).state
        == expected_cleaning
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_temperature_error"
        ).state
        == expected_e1
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_low_temperature"
        ).state
        == expected_cl
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_high_temperature"
        ).state
        == expected_ch
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_low_humidity"
        ).state
        == expected_lo
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_coil_freeze_defrost"
        ).state
        == expected_coil
    )
    assert (
        hass.states.get(
            "binary_sensor.deshumidificateur_silencieux_omnidry_20l_avec_mode_linge_motor_fault"
        ).state
        == expected_motor
    )
