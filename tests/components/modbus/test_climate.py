"""The tests for the Modbus climate component."""
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import HVAC_MODE_AUTO
from homeassistant.components.modbus.const import CONF_CLIMATES, CONF_TARGET_TEMP
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.core import State

from .conftest import ReadResult, base_config_test, base_test, prepare_service_update

from tests.common import mock_restore_cache


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: "test_climate",
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: "test_climate",
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_SCAN_INTERVAL: 20,
                    CONF_COUNT: 2,
                }
            ],
        },
    ],
)
async def test_config_climate(hass, mock_modbus):
    """Run configuration test for climate."""
    assert CLIMATE_DOMAIN in hass.config.components


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
            CONF_ADDRESS: 117,
            CONF_COUNT: 2,
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
                CONF_ADDRESS: 117,
                CONF_SLAVE: 10,
            }
        ]
    }
    mock_pymodbus.read_input_registers.return_value = ReadResult([0x00])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": entity_id}, blocking=True
    )
    assert hass.states.get(entity_id).state == "auto"


async def test_restore_state_climate(hass):
    """Run test for sensor restore state."""

    climate_name = "test_climate"
    test_temp = 37
    entity_id = f"{CLIMATE_DOMAIN}.{climate_name}"
    test_value = State(entity_id, 35)
    test_value.attributes = {ATTR_TEMPERATURE: test_temp}
    config_sensor = {
        CONF_NAME: climate_name,
        CONF_TARGET_TEMP: 117,
        CONF_ADDRESS: 117,
    }
    mock_restore_cache(
        hass,
        (test_value,),
    )
    await base_config_test(
        hass,
        config_sensor,
        climate_name,
        CLIMATE_DOMAIN,
        CONF_CLIMATES,
        None,
        method_discovery=True,
    )
    state = hass.states.get(entity_id)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes[ATTR_TEMPERATURE] == test_temp
