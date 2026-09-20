"""Test Tuya sensor platform."""

from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.tuya.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, json
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
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR]):
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


@pytest.mark.parametrize("mock_device_code", ["zndb_au1qr4dpyuqsz6vu"])
async def test_indexed_phase_child_devices(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test indexed phase sensors are grouped under stable child devices."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_device.id), mock_config_entry.entry_id
    )
    assert parent is not None

    children = dr.async_entries_for_parent_device(device_registry, parent.id)
    assert len(children) == 6
    assert not any(
        "phase_s" in entry.unique_id
        for entry in er.async_entries_for_device(entity_registry, parent.id)
    )
    child_ids = {next(iter(child.identifiers)): child.id for child in children}
    assert set(child_ids) == {
        (DOMAIN, f"{mock_device.id}_channel_{index}") for index in range(1, 7)
    }
    for child in children:
        assert child.parent_device_id == parent.id
        assert len(er.async_entries_for_device(entity_registry, child.id)) == 6

    expected_states = {
        "apparentpower": "0.22",
        "electriccurrent": "1.1",
        "power": "0.21",
        "powerfactor": "0.95",
        "reactivepower": "0.05",
        "voltage": "230.1",
    }
    for key, expected_state in expected_states.items():
        entity_id = entity_registry.async_get_entity_id(
            Platform.SENSOR,
            DOMAIN,
            f"tuya.{mock_device.id}phase_s1{key}",
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    with patch(
        "homeassistant.components.tuya.coordinator.Manager", return_value=mock_manager
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    reloaded_parent = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_device.id), mock_config_entry.entry_id
    )
    assert reloaded_parent is not None
    reloaded_children = dr.async_entries_for_parent_device(
        device_registry, reloaded_parent.id
    )
    assert {
        next(iter(child.identifiers)): child.id for child in reloaded_children
    } == child_ids
    assert all(
        child.parent_device_id == reloaded_parent.id for child in reloaded_children
    )


@pytest.mark.parametrize(
    "mock_device_code",
    ["mcs_8yhypbo7"],
)
@pytest.mark.parametrize(
    ("updates", "expected_state", "last_reported"),
    [
        # Update without dpcode - state should not change, last_reported stays
        # at available_reported
        ({"doorcontact_state": True}, "62.0", "2024-01-01T00:00:20+00:00"),
        # Update with dpcode - state should change, last_reported advances
        ({"battery_percentage": 50}, "50.0", "2024-01-01T00:01:00+00:00"),
        # Update with multiple properties including dpcode - state should change
        (
            {"doorcontact_state": True, "battery_percentage": 50},
            "50.0",
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
        entity_id="sensor.boite_aux_lettres_arriere_battery",
        dpcode="battery_percentage",
        initial_state="62.0",
        updates=updates,
        expected_state=expected_state,
        last_reported=last_reported,
    )


@pytest.mark.parametrize("mock_device_code", ["cz_guitoc9iylae4axs"])
async def test_delta_report_sensor(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    notification_helper: TuyaNotificationHelper,
) -> None:
    """Test delta report sensor behavior."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)
    entity_id = "sensor.ha_socket_delta_test_total_energy"
    timestamp = 1000

    # Delta sensors start from zero and accumulate values
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "0"
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING

    # Send delta update
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": 200},
        {"add_ele": timestamp},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.2)

    # Send delta update (multiple dpcode)
    timestamp += 100
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": 300, "switch_1": True},
        {"add_ele": timestamp, "switch_1": timestamp},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.5)

    # Send delta update (timestamp not incremented)
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": 500},
        {"add_ele": timestamp},  # same timestamp
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.5)  # unchanged

    # Send delta update (unrelated dpcode)
    await notification_helper.async_send_device_update(
        mock_device,
        {"switch_1": False},
        {"switch_1": timestamp + 100},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.5)  # unchanged

    # Send delta update
    timestamp += 100
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": 100},
        {"add_ele": timestamp},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.6)

    # Send delta update (None value)
    timestamp += 100
    mock_device.status["add_ele"] = None
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": None},
        {"add_ele": timestamp},
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.6)  # unchanged

    # Send delta update (no timestamp - skipped)
    mock_device.status["add_ele"] = 200
    await notification_helper.async_send_device_update(
        mock_device,
        {"add_ele": 200},
        None,
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == pytest.approx(0.6)  # unchanged


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
            "dlq_0tnvg2xaisqdadcf",
            "sensor.yi_lu_dai_ji_liang_ci_bao_chi_tong_duan_qi_total_energy",
            "add_ele",
            "invalid_uom",
            (
                "Incompatible unit invalid_uom replaced by entity description "
                "unit kWh for device class energy in sensor entity "
                "tuya.fcdadqsiax2gvnt0qldadd_ele; use a quirk "
                "(https://github.com/home-assistant-libs/tuya-device-handlers) "
                "to override"
            ),
        ),
        (
            "hjjcy_9f8pjxsmaqnk2tzr",
            "sensor.mt15_mt29_temperature",
            "temp_current",
            "invalid_uom",
            (
                "Device class temperature ignored for incompatible unit invalid_uom "
                "in sensor entity tuya.rzt2knqamsxjp8f9ycjjhtemp_current"
            ),
        ),
        (
            "qxj_xbwbniyt6bgws9ia",
            "sensor.sws_16600_wifi_sh_air_pressure",
            "atmospheric_pressture",
            "invalid_uom",
            (
                "Device class pressure ignored for incompatible unit invalid_uom "
                "in sensor entity tuya.ai9swgb6tyinbwbxjxqatmospheric_pressture"
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
            "14.0",
            id="device_c_ha_c",
        ),
        pytest.param(
            "c",
            US_CUSTOMARY_SYSTEM,
            "57.2",
            id="device_c_ha_f",
        ),
        pytest.param(
            "f",
            METRIC_SYSTEM,
            "-10.0",
            id="device_f_ha_c",
        ),
        pytest.param(
            "f",
            US_CUSTOMARY_SYSTEM,
            "14.0",
            id="device_f_ha_f",
        ),
    ],
)
async def test_temp_unit_convert_sensor(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    temp_unit_convert: str,
    ha_unit_system: UnitSystem,
    expected_value: str,
) -> None:
    """Test temperature sensors respect TEMP_UNIT_CONVERT and HA unit system."""
    hass.config.units = ha_unit_system
    mock_device.status["temp_unit_convert"] = temp_unit_convert
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.inverter_pool_heat_pump_outside_temperature")
    assert state is not None
    assert state.state == expected_value


@pytest.mark.parametrize("mock_device_code", ["znrb_gpzittzfnzhduquz"])
async def test_temp_unit_convert_sensor_invalid(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that device class is removed when TEMP_UNIT_CONVERT is an invalid value."""
    mock_device.status["temp_unit_convert"] = "k"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get("sensor.inverter_pool_heat_pump_temperature")
    assert state is not None
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("unit_of_measurement") == ""
    assert (
        "Device class temperature ignored for incompatible unit  in "
        "sensor entity tuya.zuqudhznfzttizpgbrnztemp_current"
    ) in caplog.text
