"""The tests for the Modbus climate component."""
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.modbus.const import (
    CONF_CLIMATES,
    CONF_CURRENT_TEMP,
    CONF_DATA_COUNT,
    CONF_TARGET_TEMP,
)
from homeassistant.const import CONF_NAME, CONF_SLAVE

from .conftest import base_test


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            "auto",
        ),
    ],
)
async def test_temperature_climate(hass, ModbusHubMock, regs, expected):
    """Run test for given config."""
    cover_name = "modbus_test_climate"
    await base_test(
        cover_name,
        hass,
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: cover_name,
                    CONF_SLAVE: 1,
                    CONF_TARGET_TEMP: 117,
                    CONF_CURRENT_TEMP: 117,
                    CONF_DATA_COUNT: 2,
                },
            ]
        },
        CLIMATE_DOMAIN,
        5,
        regs,
        expected,
        method_discovery=True,
    )
