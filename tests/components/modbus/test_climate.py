"""The tests for the Modbus climate component."""
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import HVAC_MODE_AUTO
from homeassistant.components.modbus.const import (
    CONF_CLIMATES,
    CONF_DATA_TYPE,
    CONF_TARGET_TEMP,
    DATA_TYPE_FLOAT32,
    DATA_TYPE_FLOAT64,
    DATA_TYPE_INT16,
    DATA_TYPE_INT32,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
)
from homeassistant.core import State

from .conftest import ReadResult, base_test, prepare_service_update

CLIMATE_NAME = "test_climate"
ENTITY_ID = f"{CLIMATE_DOMAIN}.{CLIMATE_NAME}"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: CLIMATE_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: CLIMATE_NAME,
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
    CLIMATE_NAME = "modbus_test_climate"
    return
    state = await base_test(
        hass,
        {
            CONF_NAME: CLIMATE_NAME,
            CONF_SLAVE: 1,
            CONF_TARGET_TEMP: 117,
            CONF_ADDRESS: 117,
            CONF_COUNT: 2,
        },
        CLIMATE_NAME,
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

    config = {
        CONF_CLIMATES: [
            {
                CONF_NAME: CLIMATE_NAME,
                CONF_TARGET_TEMP: 117,
                CONF_ADDRESS: 117,
                CONF_SLAVE: 10,
                CONF_SCAN_INTERVAL: 0,
            }
        ]
    }
    mock_pymodbus.read_input_registers.return_value = ReadResult([0x00])
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert hass.states.get(ENTITY_ID).state == "auto"


@pytest.mark.parametrize(
    "data_type, temperature, result",
    [
        (DATA_TYPE_INT16, 35, [0x00]),
        (DATA_TYPE_INT32, 36, [0x00, 0x00]),
        (DATA_TYPE_FLOAT32, 37.5, [0x00, 0x00]),
        (DATA_TYPE_FLOAT64, "39", [0x00, 0x00, 0x00, 0x00]),
    ],
)
async def test_service_climate_set_temperature(
    hass, data_type, temperature, result, mock_pymodbus
):
    """Run test for service homeassistant.update_entity."""
    config = {
        CONF_CLIMATES: [
            {
                CONF_NAME: CLIMATE_NAME,
                CONF_TARGET_TEMP: 117,
                CONF_ADDRESS: 117,
                CONF_SLAVE: 10,
                CONF_DATA_TYPE: data_type,
            }
        ]
    }
    mock_pymodbus.read_holding_registers.return_value = ReadResult(result)
    await prepare_service_update(
        hass,
        config,
    )
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            "entity_id": ENTITY_ID,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )


test_value = State(ENTITY_ID, 35)
test_value.attributes = {ATTR_TEMPERATURE: 37}


@pytest.mark.parametrize(
    "mock_test_state",
    [(test_value,)],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: CLIMATE_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SCAN_INTERVAL: 0,
                }
            ],
        },
    ],
)
async def test_restore_state_climate(hass, mock_test_state, mock_modbus):
    """Run test for sensor restore state."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVAC_MODE_AUTO
    assert state.attributes[ATTR_TEMPERATURE] == 37
