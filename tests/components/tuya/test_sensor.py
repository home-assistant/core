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
from homeassistant.helpers import entity_registry as er, issue_registry as ir, json
from homeassistant.util import json as json_util

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.SENSOR]):
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
        "has_issue",
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
                "tuya.fcdadqsiax2gvnt0qldadd_ele; this will stop working "
                "in 2026.12; use a quirk (https://github.com/home-assistant-libs"
                "/tuya-device-handlers) to override"
            ),
            True,
        ),
        (
            "znrb_gpzittzfnzhduquz",
            "sensor.inverter_pool_heat_pump_temperature",
            "temp_set",
            "",
            (
                "Device class temperature ignored for incompatible unit  in "
                "sensor entity tuya.zuqudhznfzttizpgbrnztemp_current"
            ),
            False,
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
    has_issue: bool,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid unit of measurement."""
    values = json_util.json_loads_object(mock_device.status_range[dpcode].values)
    original_unit = values.get("unit")
    values["unit"] = tuya_uom
    mock_device.status_range[dpcode].values = json.json_dumps(values)
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    state = hass.states.get(entity_id)
    assert state is not None, f"{entity_id} does not exist"
    assert expected_msg in caplog.text
    entity = entity_registry.async_get(entity_id)

    # Issue gets added when the entity description overrides the unit to a compatible one
    issue = issue_registry.async_get_issue(
        DOMAIN, f"{entity.unique_id}_incompatible_unit"
    )
    assert bool(issue) == has_issue

    # Issue gets cleared when a compatible unit is restored and the entry is reloaded
    values["unit"] = original_unit
    mock_device.status_range[dpcode].values = json.json_dumps(values)
    with patch(
        "homeassistant.components.tuya.coordinator.Manager", return_value=mock_manager
    ):
        await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert (
        issue_registry.async_get_issue(DOMAIN, f"{entity.unique_id}_incompatible_unit")
        is None
    )
