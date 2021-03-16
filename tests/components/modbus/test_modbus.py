"""The tests for the Modbus sensor component."""
from unittest import mock

import pytest

from homeassistant.components.modbus import number as number_helper
from homeassistant.components.modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    CONF_TYPE_SERIAL,
    CONF_TYPE_TCP,
    CONF_TYPE_TCPSERVER,
    MODBUS_DOMAIN as DOMAIN,
)
from homeassistant.components.modbus.modbus import (
    ModbusClientHub,
    ModbusHub,
    ModbusServerHub,
)
from homeassistant.const import (
    CONF_DELAY,
    CONF_HOST,
    CONF_METHOD,
    CONF_NAME,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_TYPE,
)

from .conftest import base_config_test


def test_number_helper():
    """Test number method."""
    assert number_helper(5) == 5
    assert number_helper(5.1) == 5.1
    assert number_helper("5") == 5
    assert number_helper("5.1") == 5.1

    with pytest.raises(Exception) as ex:
        number_helper("not a number")

    assert "invalid number" in str(ex)


@pytest.mark.parametrize("do_discovery", [False, True])
@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize(
    "do_type", [CONF_TYPE_TCP, CONF_TYPE_TCPSERVER, CONF_TYPE_SERIAL]
)
@mock.patch("homeassistant.components.modbus.modbus.StartTcpServer")
async def test_config_modbus(mock_server, hass, do_discovery, do_options, do_type):
    """Run test for modbus."""
    if do_type == CONF_TYPE_TCP or do_type == CONF_TYPE_TCPSERVER:
        config = {
            DOMAIN: {
                CONF_TYPE: do_type,
                CONF_HOST: "modbusTestHost",
                CONF_PORT: 5501,
            },
        }
    else:
        config = {
            DOMAIN: {
                CONF_TYPE: do_type,
                CONF_BAUDRATE: 9600,
                CONF_BYTESIZE: 8,
                CONF_METHOD: "rtu",
                CONF_PORT: "usb01",
                CONF_PARITY: "E",
                CONF_STOPBITS: 1,
            },
        }

    if do_options:
        config.update(
            {
                CONF_NAME: "modbusTest",
                CONF_TIMEOUT: 30,
                CONF_DELAY: 10,
            }
        )
    await base_config_test(
        hass,
        None,
        "",
        DOMAIN,
        None,
        None,
        method_discovery=do_discovery,
        config_modbus=config,
    )

    if do_type == CONF_TYPE_TCPSERVER:
        mock_server.assert_called_once_with(
            mock.ANY,
            address=("modbusTestHost", 5501),
            allow_reuse_address=True,
            defer_start=True,
        )


@pytest.mark.parametrize("is_server", [False, True])
def test_modbus_hub_wrapper(is_server):
    """Test Modbus Hub Wrapper class."""
    config = {
        CONF_TYPE: CONF_TYPE_TCPSERVER if is_server else CONF_TYPE_TCP,
        CONF_HOST: "modbusTestHost",
        CONF_PORT: 5501,
        CONF_NAME: "modbus",
        CONF_TIMEOUT: 10,
        CONF_DELAY: 1,
    }
    hub = ModbusHub(config, mock.MagicMock())

    if is_server:
        assert isinstance(hub._hub, ModbusServerHub)
    else:
        assert isinstance(hub._hub, ModbusClientHub)
