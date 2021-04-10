"""The tests for the Modbus sensor component."""
import pytest

from homeassistant.components.modbus.const import (
    CONF_BAUDRATE,
    CONF_BYTESIZE,
    CONF_PARITY,
    CONF_STOPBITS,
    MODBUS_DOMAIN as DOMAIN,
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


@pytest.mark.parametrize("do_discovery", [False, True])
@pytest.mark.parametrize(
    "do_options",
    [
        {},
        {
            CONF_NAME: "modbusTest",
            CONF_TIMEOUT: 30,
            CONF_DELAY: 10,
        },
    ],
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_TYPE: "tcp",
            CONF_HOST: "modbusTestHost",
            CONF_PORT: 5501,
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
    ],
)
async def test_config_modbus(hass, do_discovery, do_options, do_config):
    """Run test for modbus."""
    config = {
        DOMAIN: {
            **do_config,
            **do_options,
        }
    }
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
