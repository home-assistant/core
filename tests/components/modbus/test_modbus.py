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
@pytest.mark.parametrize("do_options", [False, True])
@pytest.mark.parametrize("do_type", ["tcp", "serial"])
async def test_config_modbus(hass, do_discovery, do_options, do_type):
    """Run test for modbus."""
    if do_type == "tcp":
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
