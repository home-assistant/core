"""The tests for the Modbus climate component."""
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    HVACMode,
)
from homeassistant.components.modbus.const import (
    CONF_CLIMATES,
    CONF_DATA_TYPE,
    CONF_HVAC_MODE_AUTO,
    CONF_HVAC_MODE_COOL,
    CONF_HVAC_MODE_DRY,
    CONF_HVAC_MODE_FAN_ONLY,
    CONF_HVAC_MODE_HEAT,
    CONF_HVAC_MODE_HEAT_COOL,
    CONF_HVAC_MODE_OFF,
    CONF_HVAC_MODE_REGISTER,
    CONF_HVAC_MODE_VALUES,
    CONF_HVAC_ONOFF_REGISTER,
    CONF_LAZY_ERROR,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_WRITE_REGISTERS,
    MODBUS_DOMAIN,
    DataType,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult, do_next_cycle

ENTITY_ID = f"{CLIMATE_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_SCAN_INTERVAL: 20,
                    CONF_DATA_TYPE: DataType.INT32,
                    CONF_LAZY_ERROR: 10,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 12,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 12,
                    CONF_TARGET_TEMP_WRITE_REGISTERS: True,
                    CONF_WRITE_REGISTERS: True,
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 12,
                    CONF_HVAC_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_HVAC_MODE_VALUES: {
                            "state_off": 0,
                            "state_heat": 1,
                            "state_cool": 2,
                            "state_heat_cool": 3,
                            "state_dry": 4,
                            "state_fan_only": 5,
                            "state_auto": 6,
                        },
                    },
                }
            ],
        },
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 12,
                    CONF_HVAC_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_WRITE_REGISTERS: True,
                        CONF_HVAC_MODE_VALUES: {
                            "state_off": 0,
                            "state_heat": 1,
                            "state_cool": 2,
                            "state_heat_cool": 3,
                            "state_dry": 4,
                            "state_fan_only": 5,
                            "state_auto": 6,
                        },
                    },
                }
            ],
        },
    ],
)
async def test_config_climate(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for climate."""
    assert CLIMATE_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_HVAC_MODE_VALUES: {
                            CONF_HVAC_MODE_OFF: 0,
                            CONF_HVAC_MODE_HEAT: 1,
                            CONF_HVAC_MODE_COOL: 2,
                            CONF_HVAC_MODE_HEAT_COOL: 3,
                            CONF_HVAC_MODE_AUTO: 4,
                            CONF_HVAC_MODE_FAN_ONLY: 5,
                        },
                    },
                }
            ],
        },
    ],
)
async def test_config_hvac_mode_register(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for mode register."""
    state = hass.states.get(ENTITY_ID)
    assert HVACMode.OFF in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.HEAT in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.COOL in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.HEAT_COOL in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.AUTO in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.FAN_ONLY in state.attributes[ATTR_HVAC_MODES]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 11,
                }
            ],
        },
    ],
)
async def test_config_hvac_onoff_register(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for On/Off register."""
    state = hass.states.get(ENTITY_ID)
    assert HVACMode.OFF in state.attributes[ATTR_HVAC_MODES]
    assert HVACMode.AUTO in state.attributes[ATTR_HVAC_MODES]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_SLAVE: 1,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_DATA_TYPE: DataType.INT32,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "expected"),
    [
        (
            [0x00, 0x00],
            "auto",
        ),
    ],
)
async def test_temperature_climate(
    hass: HomeAssistant, expected, mock_do_cycle
) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    ("do_config", "result", "register_words"),
    [
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 0,
                                CONF_HVAC_MODE_HEAT: 1,
                                CONF_HVAC_MODE_DRY: 2,
                            },
                        },
                    },
                ]
            },
            HVACMode.COOL,
            [0x00],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 0,
                                CONF_HVAC_MODE_HEAT: 1,
                                CONF_HVAC_MODE_DRY: 2,
                            },
                        },
                    },
                ]
            },
            HVACMode.HEAT,
            [0x01],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 0,
                                CONF_HVAC_MODE_HEAT: 2,
                                CONF_HVAC_MODE_DRY: 3,
                            },
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                    },
                ]
            },
            HVACMode.OFF,
            [0x00],
        ),
    ],
)
async def test_service_climate_update(
    hass: HomeAssistant, mock_modbus, mock_ha, result, register_words
) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus.read_holding_registers.return_value = ReadResult(register_words)
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == result


@pytest.mark.parametrize(
    ("temperature", "result", "do_config"),
    [
        (
            35,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT16,
                    }
                ]
            },
        ),
        (
            36,
            [0x00, 0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT32,
                    }
                ]
            },
        ),
        (
            37.5,
            [0x00, 0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.FLOAT32,
                    }
                ]
            },
        ),
        (
            "39",
            [0x00, 0x00, 0x00, 0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.FLOAT64,
                    }
                ]
            },
        ),
        (
            25,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_DATA_TYPE: DataType.INT16,
                        CONF_TARGET_TEMP_WRITE_REGISTERS: True,
                    }
                ]
            },
        ),
    ],
)
async def test_service_climate_set_temperature(
    hass: HomeAssistant, temperature, result, mock_modbus, mock_ha
) -> None:
    """Test set_temperature."""
    mock_modbus.read_holding_registers.return_value = ReadResult(result)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_temperature",
        {
            "entity_id": ENTITY_ID,
            ATTR_TEMPERATURE: temperature,
        },
        blocking=True,
    )


@pytest.mark.parametrize(
    ("hvac_mode", "result", "do_config"),
    [
        (
            HVACMode.COOL,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 1,
                                CONF_HVAC_MODE_HEAT: 2,
                            },
                        },
                    }
                ]
            },
        ),
        (
            HVACMode.HEAT,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 1,
                                CONF_HVAC_MODE_HEAT: 2,
                            },
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                    }
                ]
            },
        ),
        (
            HVACMode.HEAT,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 1,
                                CONF_HVAC_MODE_HEAT: 2,
                            },
                            CONF_WRITE_REGISTERS: True,
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                    }
                ]
            },
        ),
        (
            HVACMode.OFF,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_HVAC_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_HVAC_MODE_VALUES: {
                                CONF_HVAC_MODE_COOL: 1,
                                CONF_HVAC_MODE_HEAT: 2,
                            },
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                        CONF_WRITE_REGISTERS: True,
                    }
                ]
            },
        ),
    ],
)
async def test_service_set_mode(
    hass: HomeAssistant, hvac_mode, result, mock_modbus, mock_ha
) -> None:
    """Test set mode."""
    mock_modbus.read_holding_registers.return_value = ReadResult(result)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        "set_hvac_mode",
        {
            "entity_id": ENTITY_ID,
            ATTR_HVAC_MODE: hvac_mode,
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
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SCAN_INTERVAL: 0,
                }
            ],
        },
    ],
)
async def test_restore_state_climate(
    hass: HomeAssistant, mock_test_state, mock_modbus
) -> None:
    """Run test for sensor restore state."""
    state = hass.states.get(ENTITY_ID)
    assert state.state == HVACMode.AUTO
    assert state.attributes[ATTR_TEMPERATURE] == 37


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_LAZY_ERROR: 1,
                }
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "do_exception", "start_expect", "end_expect"),
    [
        (
            [0x8000],
            True,
            "17",
            STATE_UNAVAILABLE,
        ),
    ],
)
async def test_lazy_error_climate(
    hass: HomeAssistant, mock_do_cycle: FrozenDateTimeFactory, start_expect, end_expect
) -> None:
    """Run test for sensor."""
    hass.states.async_set(ENTITY_ID, 17)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == start_expect
    await do_next_cycle(hass, mock_do_cycle, 11)
    assert hass.states.get(ENTITY_ID).state == start_expect
    await do_next_cycle(hass, mock_do_cycle, 11)
    assert hass.states.get(ENTITY_ID).state == end_expect


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_CLIMATES: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_TARGET_TEMP: 117,
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                }
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("config_addon", "register_words"),
    [
        (
            {
                CONF_DATA_TYPE: DataType.INT16,
            },
            [7, 9],
        ),
        (
            {
                CONF_DATA_TYPE: DataType.INT32,
            },
            [7],
        ),
    ],
)
async def test_wrong_unpack_climate(hass: HomeAssistant, mock_do_cycle) -> None:
    """Run test for sensor."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_no_discovery_info_climate(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert CLIMATE_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {CLIMATE_DOMAIN: {"platform": MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert CLIMATE_DOMAIN in hass.config.components
