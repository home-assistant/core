"""The tests for the Modbus sensor component."""
import logging
from unittest import mock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.modbus.const import (
    ATTR_ADDRESS,
    ATTR_HUB,
    ATTR_STATE,
    ATTR_UNIT,
    ATTR_VALUE,
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    DEFAULT_HUB,
    MODBUS_DOMAIN as DOMAIN,
    SERVICE_WRITE_COIL,
    SERVICE_WRITE_REGISTER,
)
from homeassistant.components.modbus.modbus import ModbusHub
from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
)
from homeassistant.setup import async_setup_component

from .conftest import ReadResult


async def _config_helper(hass, do_config):
    """Run test for modbus."""

    config = {DOMAIN: do_config}

    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient"
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusSerialClient"
    ), mock.patch(
        "homeassistant.components.modbus.modbus.ModbusUdpClient"
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "udp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
        },
        {
            CONF_TYPE: "rtuovertcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
    ],
)
async def test_config_modbus(hass, caplog, do_config):
    """Run test for modbus."""

    caplog.set_level(logging.ERROR)
    await _config_helper(hass, do_config)
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0


async def test_config_multiple_modbus(hass, caplog):
    """Run test for multiple modbus."""

    do_config = [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest1",
        },
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
            CONF_NAME: "modbusTest2",
        },
        {
            CONF_TYPE: "serial",
            CONF_BAUDRATE: 9600,
            CONF_BYTESIZE: 8,
            CONF_METHOD: "rtu",
            CONF_PORT: "usb01",
            CONF_PARITY: "E",
            CONF_STOPBITS: 1,
            CONF_NAME: "modbusTest3",
        },
    ]

    caplog.set_level(logging.ERROR)
    await _config_helper(hass, do_config)
    assert DOMAIN in hass.config.components
    assert len(caplog.records) == 0


@pytest.fixture()
def modbus_hub():
    """Return class obj configured."""

    config_hub = {
        CONF_NAME: DEFAULT_HUB,
        CONF_TYPE: "tcp",
        CONF_HOST: "modbusTest",
        CONF_PORT: 5001,
        CONF_DELAY: 1,
        CONF_TIMEOUT: 1,
    }
    hub = ModbusHub(config_hub)
    assert hub.name == config_hub[CONF_NAME]
    return hub


async def test_pb_create_exception(hass, caplog, modbus_hub):
    """Run general test of class modbusHub."""

    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient"
    ) as mock_pb:
        caplog.set_level(logging.DEBUG)
        mock_pb.side_effect = ModbusException("test no class")
        modbus_hub.setup()
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"


async def test_pb_connect(hass, caplog, modbus_hub):
    """Run general test of class modbusHub."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        caplog.set_level(logging.DEBUG)
        modbus_hub.setup()
        assert mock_pb.connect.called
        assert len(caplog.records) == 0
        caplog.clear()

        mock_pb.connect.side_effect = ModbusException("test failed connect()")
        modbus_hub.setup()
        assert mock_pb.connect.called
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"


async def test_pb_close(hass, caplog, modbus_hub):
    """Run general test of class modbusHub."""

    caplog.set_level(logging.DEBUG)
    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        caplog.clear()
        modbus_hub.setup()
        modbus_hub.close()
        assert mock_pb.close.called
        assert len(caplog.records) == 0

        mock_pb.close.side_effect = ModbusException("test failed close()")
        modbus_hub.setup()
        caplog.clear()
        modbus_hub.close()
        assert mock_pb.close.called
        assert len(caplog.records) == 1
        assert caplog.records[0].levelname == "ERROR"


async def test_pb_read_coils(hass, modbus_hub):
    """Run test for pymodbus read_coils calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        data = [0x15]
        mock_pb.read_coils.return_value = ReadResult(data)
        result = modbus_hub.read_coils(None, 17, 1)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_coils.return_value = ReadResult(data)
        result = modbus_hub.read_coils(None, 17, 2)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_coils.side_effect = ModbusException("fail read_coils")
        result = modbus_hub.read_coils(None, 17, 2)
        assert result is None


async def test_pb_read_discrete_inputs(hass, modbus_hub):
    """Run test for pymodbus read_coils calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        data = [0x15]
        mock_pb.read_discrete_inputs.return_value = ReadResult(data)
        result = modbus_hub.read_discrete_inputs(None, 17, 1)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_discrete_inputs.return_value = ReadResult(data)
        result = modbus_hub.read_discrete_inputs(None, 17, 2)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_discrete_inputs.side_effect = ModbusException("fail read_coils")
        result = modbus_hub.read_discrete_inputs(None, 17, 2)
        assert result is None


async def test_pb_read_input_registers(hass, modbus_hub):
    """Run test for pymodbus read_input_registers calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        data = [0x15]
        mock_pb.read_input_registers.return_value = ReadResult(data)
        result = modbus_hub.read_input_registers(None, 17, 1)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_input_registers.return_value = ReadResult(data)
        result = modbus_hub.read_input_registers(None, 17, 2)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_input_registers.side_effect = ModbusException("fail read_coils")
        result = modbus_hub.read_input_registers(None, 17, 2)
        assert result is None


async def test_pb_read_holding_registers(hass, modbus_hub):
    """Run test for pymodbus read_holding_registers calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        data = [0x15]
        mock_pb.read_holding_registers.return_value = ReadResult(data)
        result = modbus_hub.read_holding_registers(None, 17, 1)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_holding_registers.return_value = ReadResult(data)
        result = modbus_hub.read_holding_registers(None, 17, 2)
        assert result.registers == data

        data = [0x15, 0x16]
        mock_pb.read_holding_registers.side_effect = ModbusException("fail read_coils")
        result = modbus_hub.read_holding_registers(None, 17, 2)
        assert result is None


async def test_pb_write_coil(hass, modbus_hub):
    """Run test for pymodbus write_coil calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        addr = 17
        data = 16
        assert modbus_hub.write_coil(None, addr, data)
        assert mock_pb.write_coil.called
        assert mock_pb.write_coil.call_args[0] == (addr, data)

        mock_pb.write_coil.side_effect = ModbusException("fail write_coil")
        assert not modbus_hub.write_coil(None, addr, data)


async def test_pb_write_coils(hass, modbus_hub):
    """Run test for pymodbus write_coils calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        addr = 17
        data = 16
        assert modbus_hub.write_coils(None, addr, data)
        assert mock_pb.write_coils.called
        assert mock_pb.write_coils.call_args[0] == (addr, data)

        mock_pb.write_coils.side_effect = ModbusException("fail write_coils")
        assert not modbus_hub.write_coils(None, addr, data)


async def test_pb_write_register(hass, modbus_hub):
    """Run test for pymodbus write_register calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        addr = 17
        data = 16
        assert modbus_hub.write_register(None, addr, data)
        assert mock_pb.write_register.called
        assert mock_pb.write_register.call_args[0] == (addr, data)

        mock_pb.write_register.side_effect = ModbusException("fail write_")
        assert not modbus_hub.write_register(None, addr, data)


async def test_pb_write_registers(hass, modbus_hub):
    """Run test for pymodbus write_registers calls."""

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        modbus_hub.setup()

        addr = 17
        data = 16
        assert modbus_hub.write_registers(None, addr, data)
        assert mock_pb.write_registers.called
        assert mock_pb.write_registers.call_args[0] == (addr, data)

        mock_pb.write_registers.side_effect = ModbusException("fail write_")
        assert not modbus_hub.write_registers(None, addr, data)


async def test_pb_service_write_register(hass):
    """Run test for service write_register."""

    conf_name = "myModbus"
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: conf_name,
            }
        ]
    }

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

        data = {ATTR_HUB: conf_name, ATTR_UNIT: 17, ATTR_ADDRESS: 16, ATTR_VALUE: 15}
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )
        assert mock_pb.write_register.called
        assert mock_pb.write_register.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_VALUE],
        )

        data[ATTR_VALUE] = [1, 2, 3]
        await hass.services.async_call(
            DOMAIN, SERVICE_WRITE_REGISTER, data, blocking=True
        )
        assert mock_pb.write_registers.called
        assert mock_pb.write_registers.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_VALUE],
        )


async def test_pb_service_write_coil(hass):
    """Run test for service write_coil."""

    conf_name = "myModbus"
    config = {
        DOMAIN: [
            {
                CONF_TYPE: "tcp",
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
                CONF_NAME: conf_name,
            }
        ]
    }

    mock_pb = mock.MagicMock()
    with mock.patch(
        "homeassistant.components.modbus.modbus.ModbusTcpClient", return_value=mock_pb
    ):
        assert await async_setup_component(hass, DOMAIN, config) is True
        await hass.async_block_till_done()

        data = {ATTR_HUB: conf_name, ATTR_UNIT: 17, ATTR_ADDRESS: 16, ATTR_STATE: False}
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert mock_pb.write_coil.called
        assert mock_pb.write_coil.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_STATE],
        )

        data[ATTR_STATE] = [True, False, True]
        await hass.services.async_call(DOMAIN, SERVICE_WRITE_COIL, data, blocking=True)
        assert mock_pb.write_coils.called
        assert mock_pb.write_coils.call_args[0] == (
            data[ATTR_ADDRESS],
            data[ATTR_STATE],
        )
