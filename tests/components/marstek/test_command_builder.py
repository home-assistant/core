"""Tests for the Marstek command builder."""

from __future__ import annotations

import json

from pymarstek.command_builder import (
    build_command,
    discover,
    get_battery_status,
    get_es_mode,
    get_es_status,
    get_next_request_id,
    get_pv_status,
    reset_request_id,
    set_es_mode_manual_charge,
    set_es_mode_manual_discharge,
)
from pymarstek.const import (
    CMD_BATTERY_STATUS,
    CMD_DISCOVER,
    CMD_ES_MODE,
    CMD_ES_SET_MODE,
    CMD_ES_STATUS,
    CMD_PV_GET_STATUS,
)


def test_get_next_request_id() -> None:
    """Test request ID generation."""
    reset_request_id()
    assert get_next_request_id() == 1
    assert get_next_request_id() == 2
    assert get_next_request_id() == 3


def test_reset_request_id() -> None:
    """Test request ID reset."""
    get_next_request_id()
    get_next_request_id()
    reset_request_id()
    assert get_next_request_id() == 1


def test_build_command() -> None:
    """Test building a command."""
    reset_request_id()
    command = build_command("test.method", {"param": "value"})
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == "test.method"
    assert parsed["params"] == {"param": "value"}


def test_build_command_without_params() -> None:
    """Test building a command without parameters."""
    reset_request_id()
    command = build_command("test.method")
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == "test.method"
    assert parsed["params"] == {}


def test_discover() -> None:
    """Test discover command."""
    reset_request_id()
    command = discover()
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_DISCOVER
    assert parsed["params"] == {"ble_mac": "0"}


def test_get_battery_status() -> None:
    """Test battery status command."""
    reset_request_id()
    command = get_battery_status(0)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_BATTERY_STATUS
    assert parsed["params"] == {"id": 0}


def test_get_battery_status_with_device_id() -> None:
    """Test battery status command with device ID."""
    reset_request_id()
    command = get_battery_status(5)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_BATTERY_STATUS
    assert parsed["params"] == {"id": 5}


def test_get_es_status() -> None:
    """Test ES status command."""
    reset_request_id()
    command = get_es_status(0)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_ES_STATUS
    assert parsed["params"] == {"id": 0}


def test_get_es_mode() -> None:
    """Test ES mode command."""
    reset_request_id()
    command = get_es_mode(0)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_ES_MODE
    assert parsed["params"] == {"id": 0}


def test_get_pv_status() -> None:
    """Test PV status command."""
    reset_request_id()
    command = get_pv_status(0)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_PV_GET_STATUS
    assert parsed["params"] == {"id": 0}


def test_set_es_mode_manual_charge() -> None:
    """Test manual charge mode command."""
    reset_request_id()
    command = set_es_mode_manual_charge(0, -1300)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_ES_SET_MODE
    assert parsed["params"]["id"] == 0
    assert parsed["params"]["config"]["mode"] == "Manual"
    assert parsed["params"]["config"]["manual_cfg"]["power"] == -1300
    assert parsed["params"]["config"]["manual_cfg"]["enable"] == 1
    assert parsed["params"]["config"]["manual_cfg"]["week_set"] == 127
    assert parsed["params"]["config"]["manual_cfg"]["start_time"] == "00:00"
    assert parsed["params"]["config"]["manual_cfg"]["end_time"] == "23:59"


def test_set_es_mode_manual_discharge() -> None:
    """Test manual discharge mode command."""
    reset_request_id()
    command = set_es_mode_manual_discharge(0, 1300)
    parsed = json.loads(command)

    assert parsed["id"] == 1
    assert parsed["method"] == CMD_ES_SET_MODE
    assert parsed["params"]["id"] == 0
    assert parsed["params"]["config"]["mode"] == "Manual"
    assert parsed["params"]["config"]["manual_cfg"]["power"] == 1300
    assert parsed["params"]["config"]["manual_cfg"]["enable"] == 1
    assert parsed["params"]["config"]["manual_cfg"]["week_set"] == 127


def test_set_es_mode_custom_power() -> None:
    """Test manual mode with custom power values."""
    reset_request_id()

    # Test charge with custom power
    command = set_es_mode_manual_charge(0, -2000)
    parsed = json.loads(command)
    assert parsed["params"]["config"]["manual_cfg"]["power"] == -2000

    # Test discharge with custom power
    command = set_es_mode_manual_discharge(0, 800)
    parsed = json.loads(command)
    assert parsed["params"]["config"]["manual_cfg"]["power"] == 800


def test_command_incremental_ids() -> None:
    """Test that command IDs increment correctly."""
    reset_request_id()

    cmd1 = discover()
    cmd2 = get_battery_status()
    cmd3 = get_es_mode()

    parsed1 = json.loads(cmd1)
    parsed2 = json.loads(cmd2)
    parsed3 = json.loads(cmd3)

    assert parsed1["id"] == 1
    assert parsed2["id"] == 2
    assert parsed3["id"] == 3
