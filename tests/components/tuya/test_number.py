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
from homeassistant.components.tuya.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir, json
from homeassistant.util import json as json_util

from . import TuyaNotificationHelper, check_selective_state_update, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def platform_autouse():
    """Platform fixture."""
    with patch("homeassistant.components.tuya.PLATFORMS", [Platform.NUMBER]):
        yield


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
        "has_issue",
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
                "tuya.iks13mcaiyie3rryjb2ocalarm_time; this will stop working "
                "in 2026.12; use a quirk (https://github.com/home-assistant-libs"
                "/tuya-device-handlers) to override"
            ),
            True,
        ),
        (
            "znrb_gpzittzfnzhduquz",
            "number.inverter_pool_heat_pump_temperature",
            "temp_set",
            "",
            (
                "Device class temperature ignored for incompatible unit  in "
                "number entity tuya.zuqudhznfzttizpgbrnztemp_set"
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
    mock_device.function[dpcode].values = json.json_dumps(values)
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
    mock_device.function[dpcode].values = json.json_dumps(values)
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
