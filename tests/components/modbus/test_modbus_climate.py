"""The tests for the Modbus climate component."""
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.modbus.const import (
    CONF_CLIMATES,
    CONF_CURRENT_TEMP,
    CONF_DATA_COUNT,
    CONF_TARGET_TEMP,
)
from homeassistant.const import CONF_NAME, CONF_SCAN_INTERVAL, CONF_SLAVE

from .conftest import ReadResult, base_config_test, base_test, run_service_update


@pytest.mark.parametrize(
    "do_options",
    [
        {},
        {
            CONF_SCAN_INTERVAL: 20,
            CONF_DATA_COUNT: 2,
        },
    ],
)
async def test_config_climate(hass, do_options):
    """Run test for climate."""
    device_name = "test_climate"
    device_config = {
        CONF_NAME: device_name,
        CONF_TARGET_TEMP: 117,
        CONF_CURRENT_TEMP: 117,
        CONF_SLAVE: 10,
        **do_options,
    }
    await base_config_test(
        hass,
        device_config,
        device_name,
        CLIMATE_DOMAIN,
        CONF_CLIMATES,
        None,
        method_discovery=True,
    )


@pytest.mark.parametrize(
    "regs,expected",
    [
        (
            [0x00],
            "auto",
        ),
    ],
)
async def test_temperature_climate(hass, regs, expected):
    """Run test for given config."""
    climate_name = "modbus_test_climate"
    return
    state = await base_test(
        hass,
        {
            CONF_NAME: climate_name,
            CONF_SLAVE: 1,
            CONF_TARGET_TEMP: 117,
            CONF_CURRENT_TEMP: 117,
            CONF_DATA_COUNT: 2,
        },
        climate_name,
        CLIMATE_DOMAIN,
        CONF_CLIMATES,
        None,
        regs,
        expected,
        method_discovery=True,
        scan_interval=5,
    )
    assert state == expected


async def test_service_climate_update(hass, mock_pymodbus):
    """Run test for service homeassistant.update_entity."""

    entity_id = "climate.test"
    config = {
        CONF_CLIMATES: [
            {
                CONF_NAME: "test",
                CONF_TARGET_TEMP: 117,
                CONF_CURRENT_TEMP: 117,
                CONF_SLAVE: 10,
            }
        ]
    }
    mock_pymodbus.read_input_registers.return_value = ReadResult([0x00])
    await run_service_update(
        hass,
        config,
        entity_id,
    )
    assert hass.states.get(entity_id).state == "auto"
