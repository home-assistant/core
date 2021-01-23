"""Tests for the init."""

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant.components.climate.const import (
    FAN_AUTO,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_DRY,
    HVAC_MODE_FAN_ONLY,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_FAN_MODE,
    SUPPORT_TARGET_TEMPERATURE,
)
from homeassistant.const import (
    CONF_DEVICE,
    CONF_DEVICES,
    CONF_FORCE_UPDATE,
    CONF_SCAN_INTERVAL,
)

from tests.common import MockConfigEntry

TITLE = "BRC1H"
DOMAIN = "daikin_madoka"
UNIQUE_ID = TITLE + "-id"


class _BLEDevice:
    def __init__(self, address):

        self.address = address


TEST_DEVICES = "aa:bb:cc:dd:ee:ff"
TEST_DISCOVERED_DEVICES = [_BLEDevice("aa:bb:cc:dd:ee:ff")]
FAIL_TEST_DEVICES = "XX:XX:XX:XX:XX:XX, error_string"
TEST_DEVICE = "hci0"
TEST_SCAN_INTERVAL = 15
TEST_FORCE_UPDATE = True


def prepare_fixture(fix):
    """Prepare data from fixture and add common values for assertion."""
    default_values = {
        "fan_modes": [FAN_LOW, FAN_MEDIUM, FAN_HIGH, FAN_AUTO],
        "name": "test",
        "address": TEST_DEVICES,
        "hvac_modes": [
            HVAC_MODE_FAN_ONLY,
            HVAC_MODE_DRY,
            HVAC_MODE_COOL,
            HVAC_MODE_HEAT,
            HVAC_MODE_AUTO,
            HVAC_MODE_OFF,
        ],
        "supported_features": SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE,
        "max_temp": 32,
        "min_temp": 16,
        "target_temp_step": 1,
        "device_info": {"device_id": "0.01", "firmware": "123"},
    }
    return {**fix, **default_values}


def create_controller_disconnected(fixture):
    """Create mock controller that raises ConnectionExceptions when used."""
    values = prepare_fixture(fixture)
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        from pymadoka.connection import ConnectionException, ConnectionStatus

        controller = MagicMock()
        controller.operation_mode.query.side_effect = ConnectionException(
            "Not connected"
        )
        controller.operation_mode.update.side_effect = ConnectionException(
            "Not connected"
        )
        controller.fan_speed.query.side_effect = ConnectionException("Not connected")
        controller.fan_speed.update.side_effect = ConnectionException("Not connected")
        controller.set_point.query.side_effect = ConnectionException("Not connected")
        controller.set_point.update.side_effect = ConnectionException("Not connected")
        controller.power_state.query.side_effect = ConnectionException("Not connected")
        controller.power_state.update.side_effect = ConnectionException("Not connected")
        controller.temperatures.query.side_effect = ConnectionException("Not connected")
        controller.connection.name = values["name"]
        controller.connection.address = values["address"]
        controller.connection.connection_status = ConnectionStatus.DISCONNECTED
        start = asyncio.Future()
        start.set_result(True)
        controller.start.return_value = start
        update = asyncio.Future()
        update.set_result(True)
        controller.update.return_value = update
        refresh = asyncio.Future()
        refresh.set_result(True)
        controller.refresh.return_value = refresh
        read_info = asyncio.Future()
        read_info.set_result(values["device_info"])
        controller.read_info.return_value = read_info
        return controller


def create_controller_aborted(fixture, start, update):
    """Create mock controller that raises ConnectionAbortedError when used."""
    values = prepare_fixture(fixture)
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        from pymadoka.connection import ConnectionStatus

        controller = MagicMock()
        controller.operation_mode.query.side_effect = ConnectionAbortedError(
            "Not connected"
        )
        controller.operation_mode.update.side_effect = ConnectionAbortedError(
            "Not connected"
        )
        controller.fan_speed.query.side_effect = ConnectionAbortedError("Aborted")
        controller.fan_speed.update.side_effect = ConnectionAbortedError("Aborted")
        controller.set_point.query.side_effect = ConnectionAbortedError("Aborted")
        controller.set_point.update.side_effect = ConnectionAbortedError("Aborted")
        controller.power_state.query.side_effect = ConnectionAbortedError("Aborted")
        controller.power_state.update.side_effect = ConnectionAbortedError("Aborted")
        controller.temperatures.query.side_effect = ConnectionAbortedError("Aborted")
        controller.connection.name = values["name"]
        controller.connection.address = values["address"]
        controller.connection.connection_status = ConnectionStatus.DISCONNECTED
        if start:
            controller.start.side_effect = ConnectionAbortedError("Aborted")
        else:
            start = asyncio.Future()
            start.set_result(True)
            controller.start.return_value = start
        if update:
            controller.update.side_effect = ConnectionAbortedError("Aborted")
        else:
            update = asyncio.Future()
            update.set_result(True)
            controller.update.return_value = update
        refresh = asyncio.Future()
        refresh.set_result(True)
        controller.refresh.return_value = refresh
        read_info = asyncio.Future()
        read_info.set_result(values["device_info"])
        controller.read_info.return_value = read_info
        return controller


def create_controller_update_error(fixture):
    """Create mock controller that raises ConnectionException when used to update status."""
    values = prepare_fixture(fixture)
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        from pymadoka.connection import ConnectionException, ConnectionStatus

        controller = MagicMock()
        controller.operation_mode.query.side_effect = ConnectionException(
            "Not connected"
        )
        controller.operation_mode.update.side_effect = ConnectionException(
            "Not connected"
        )
        controller.fan_speed.query.side_effect = ConnectionException("Not connected")
        controller.fan_speed.update.side_effect = ConnectionException("Not connected")
        controller.set_point.query.side_effect = ConnectionException("Not connected")
        controller.set_point.update.side_effect = ConnectionException("Not connected")
        controller.power_state.query.side_effect = ConnectionException("Not connected")
        controller.power_state.update.side_effect = ConnectionException("Not connected")
        controller.temperatures.query.side_effect = ConnectionException("Not connected")
        controller.connection.name = values["name"]
        controller.connection.address = values["address"]
        controller.connection.connection_status = ConnectionStatus.DISCONNECTED
        start = asyncio.Future()
        start.set_result(True)
        controller.start.return_value = start
        controller.update.side_effect = ConnectionException("Not connected")
        refresh = asyncio.Future()
        refresh.set_result(True)
        controller.refresh.return_value = refresh
        read_info = asyncio.Future()
        read_info.set_result(values["device_info"])
        controller.read_info.return_value = read_info
        return controller


def create_controller_empty_status(fixture):
    """Create mock controller that returns uninitialized empty status."""
    values = prepare_fixture(fixture)

    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):

        from pymadoka.connection import ConnectionStatus

        controller = MagicMock()
        controller.operation_mode.status = None
        controller.fan_speed.status = None
        controller.set_point.status = None
        controller.power_state.status = None
        controller.temperatures.status = None
        controller.connection.name = values["name"]
        controller.connection.address = values["address"]
        controller.connection.connection_status = ConnectionStatus.CONNECTED
        start = asyncio.Future()
        start.set_result(True)
        controller.start.return_value = start
        update = asyncio.Future()
        update.set_result(True)
        controller.update.return_value = update
        refresh = asyncio.Future()
        refresh.set_result(True)
        controller.refresh.return_value = refresh
        read_info = asyncio.Future()
        read_info.set_result(values["device_info"])
        controller.read_info.return_value = read_info
        return controller


def create_controller_mock(fixture):
    """Create mock controller with test values from fixture."""

    values = prepare_fixture(fixture)

    operation_mode = values["madoka"]["operation_mode"]
    fan_speed = values["madoka"]["fan_speed"]
    set_point = values["madoka"]["set_point"]
    power = values["madoka"]["power_state"]
    temperatures = values["madoka"]["temperatures"]
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock):
        from pymadoka.connection import ConnectionStatus
        from pymadoka.features.fanspeed import FanSpeedEnum, FanSpeedStatus
        from pymadoka.features.operationmode import (
            OperationModeEnum,
            OperationModeStatus,
        )
        from pymadoka.features.power import PowerStateStatus
        from pymadoka.features.setpoint import SetPointStatus
        from pymadoka.features.temperatures import TemperaturesStatus

        controller = MagicMock()
        controller.operation_mode.status = OperationModeStatus(
            OperationModeEnum[operation_mode]
        )
        controller.fan_speed.status = FanSpeedStatus(
            FanSpeedEnum[fan_speed["cooling"]], FanSpeedEnum[fan_speed["heating"]]
        )
        controller.set_point.status = SetPointStatus(
            set_point["cooling"], set_point["heating"]
        )
        controller.power_state.status = PowerStateStatus(power)
        controller.temperatures.status = TemperaturesStatus(
            temperatures["indoor"], temperatures["outdoor"]
        )

        op_mode_update = asyncio.Future()
        op_mode_update.set_result(True)
        controller.operation_mode.update.return_value = op_mode_update

        fs_update = asyncio.Future()
        fs_update.set_result(True)
        controller.fan_speed.update.return_value = fs_update

        sp_update = asyncio.Future()
        sp_update.set_result(True)
        controller.set_point.update.return_value = sp_update

        ps_update = asyncio.Future()
        ps_update.set_result(True)
        controller.power_state.update.return_value = ps_update

        controller.connection.name = values["name"]
        controller.connection.address = values["address"]
        controller.connection.connection_status = ConnectionStatus.CONNECTED
        start = asyncio.Future()
        start.set_result(True)
        controller.start.return_value = start

        update = asyncio.Future()
        update.set_result(True)
        controller.update.return_value = update
        refresh = asyncio.Future()
        refresh.set_result(True)
        controller.refresh.return_value = refresh
        read_info = asyncio.Future()
        read_info.set_result(values["device_info"])
        controller.read_info.return_value = read_info
        return controller


async def async_init_integration(
    hass,
    controller_mock,
) -> MockConfigEntry:
    """Set up the Daikin Madoka integration in Home Assistant."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=UNIQUE_ID,
        data={
            CONF_DEVICES: TEST_DEVICES,
            CONF_DEVICE: TEST_DEVICE,
            CONF_SCAN_INTERVAL: TEST_SCAN_INTERVAL,
            CONF_FORCE_UPDATE: TEST_FORCE_UPDATE,
        },
    )
    process_mock = MagicMock()
    process_mock.communicate.return_value = (b"bluetoothctl: 5.53", 0)
    with patch("subprocess.Popen", return_value=process_mock), patch(
        "homeassistant.components.daikin_madoka.config_flow.force_device_disconnect",
        return_value=True,
    ), patch(
        "homeassistant.components.daikin_madoka.config_flow.discover_devices",
        return_value=TEST_DISCOVERED_DEVICES,
    ), patch(
        "homeassistant.components.daikin_madoka.Controller",
        return_value=controller_mock,
    ):

        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)

        await hass.async_block_till_done()

    return entry
