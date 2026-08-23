"""Test Tuya number platform."""

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, json
from homeassistant.util import json as json_util
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.NUMBER]):
        yield


@pytest.mark.usefixtures("no_quirk")
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
    ["mal_gyitctrjj1kefxp2"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays
        # at available_reported
        ({"switch_alarm_sound": True}, "15.0", "2024-01-01T00:00:20+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"delay_set": 17}, "17.0", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"switch_alarm_sound": True, "delay_set": 17},
            "17.0",
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
        entity_id="number.multifunction_alarm_arm_delay",
        dpcode="delay_set",
        initial_state="15.0",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["mal_gyitctrjj1kefxp2"],
)
async def test_set_value(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test set value."""
    entity_id = "number.multifunction_alarm_arm_delay"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: entity_id,
            ATTR_VALUE: 18,
        },
        blocking=True,
    )
    mock_manager.send_commands.assert_called_once_with(
        mock_device.id, [{"code": "delay_set", "value": 18}]
    )


@pytest.mark.parametrize(
    (
        "mock_device_code",
        "entity_id",
        "dpcode",
        "tuya_uom",
        "expected_msg",
    ),
    [
        (
            "co2bj_yrr3eiyiacm31ski",
            "number.aqi_alarm_duration",
            "alarm_time",
            "invalid_uom",
            (
                "Incompatible unit invalid_uom replaced by entity description "
                "unit s for device class duration in number entity "
                "tuya.iks13mcaiyie3rryjb2ocalarm_time; use a quirk "
                "(https://github.com/home-assistant-libs/tuya-device-handlers) "
                "to override"
            ),
        ),
        (
            "znrb_gpzittzfnzhduquz",
            "number.inverter_pool_heat_pump_temperature",
            "temp_set",
            "invalid_uom",
            (
                "Device class temperature ignored for incompatible unit invalid_uom "
                "in number entity tuya.zuqudhznfzttizpgbrnztemp_set"
            ),
        ),
    ],
)
async def test_invalid_uom(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    entity_id: str,
    dpcode: str,
    tuya_uom: str,
    expected_msg: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid unit of measurement."""
    values = json_util.json_loads_object(mock_device.status_range[dpcode].values)
    values["unit"] = tuya_uom
    mock_device.function[dpcode].values = json.json_dumps(values)
    mock_device.status_range[dpcode].values = json.json_dumps(values)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert expected_msg in caplog.text


@pytest.mark.parametrize("mock_device_code", ["znrb_gpzittzfnzhduquz"])
@pytest.mark.parametrize(
    ("temp_unit_convert", "ha_unit_system", "expected_value"),
    [
        pytest.param(
            "c",
            METRIC_SYSTEM,
            "28.0",
            id="device_c_ha_c",
        ),
        pytest.param(
            "c",
            US_CUSTOMARY_SYSTEM,
            "82.4",
            id="device_c_ha_f",
        ),
        pytest.param(
            "f",
            METRIC_SYSTEM,
            "-2.2",
            id="device_f_ha_c",
        ),
        pytest.param(
            "f",
            US_CUSTOMARY_SYSTEM,
            "28.0",
            id="device_f_ha_f",
        ),
    ],
)
async def test_temp_unit_convert_number(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    temp_unit_convert: str,
    ha_unit_system: UnitSystem,
    expected_value: str,
) -> None:
    """Test temperature number entities respect TEMP_UNIT_CONVERT and HA unit system."""
    hass.config.units = ha_unit_system
    mock_device.status["temp_unit_convert"] = temp_unit_convert
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("number.inverter_pool_heat_pump_temperature")
    assert state is not None
    assert state.state == expected_value


@pytest.mark.parametrize("mock_device_code", ["znrb_gpzittzfnzhduquz"])
async def test_temp_unit_convert_number_invalid(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
) -> None:
    """Test that device class is removed when TEMP_UNIT_CONVERT is an invalid value."""
    mock_device.status["temp_unit_convert"] = "k"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("number.inverter_pool_heat_pump_temperature")
    assert state is not None
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("unit_of_measurement") == ""
