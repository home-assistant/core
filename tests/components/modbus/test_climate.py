"""The tests for the Modbus climate component."""

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODE,
    ATTR_HVAC_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_AUTO,
    FAN_DIFFUSE,
    FAN_FOCUS,
    FAN_HIGH,
    FAN_LOW,
    FAN_MEDIUM,
    FAN_MIDDLE,
    FAN_OFF,
    FAN_ON,
    FAN_TOP,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_SWING_MODE,
    SERVICE_SET_TEMPERATURE,
    SWING_BOTH,
    SWING_HORIZONTAL,
    SWING_OFF,
    SWING_ON,
    SWING_VERTICAL,
    HVACMode,
)
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.modbus.const import (
    CONF_CLIMATES,
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_FAN_MODE_AUTO,
    CONF_FAN_MODE_HIGH,
    CONF_FAN_MODE_LOW,
    CONF_FAN_MODE_MEDIUM,
    CONF_FAN_MODE_OFF,
    CONF_FAN_MODE_ON,
    CONF_FAN_MODE_REGISTER,
    CONF_FAN_MODE_TOP,
    CONF_FAN_MODE_VALUES,
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
    CONF_MAX_TEMP,
    CONF_MIN_TEMP,
    CONF_SWING_MODE_REGISTER,
    CONF_SWING_MODE_SWING_BOTH,
    CONF_SWING_MODE_SWING_HORIZ,
    CONF_SWING_MODE_SWING_OFF,
    CONF_SWING_MODE_SWING_ON,
    CONF_SWING_MODE_SWING_VERT,
    CONF_SWING_MODE_VALUES,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_WRITE_REGISTERS,
    MODBUS_DOMAIN,
    DataType,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult

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
                    CONF_DEVICE_ADDRESS: 10,
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
                    CONF_TARGET_TEMP: [130, 131, 132, 133, 135, 128, 129],
                    CONF_ADDRESS: 117,
                    CONF_SLAVE: 10,
                    CONF_HVAC_ONOFF_REGISTER: 12,
                    CONF_HVAC_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_HVAC_MODE_VALUES: {
                            CONF_HVAC_MODE_OFF: 0,
                            CONF_HVAC_MODE_HEAT: 1,
                            CONF_HVAC_MODE_COOL: 2,
                            CONF_HVAC_MODE_HEAT_COOL: 3,
                            CONF_HVAC_MODE_DRY: 4,
                            CONF_HVAC_MODE_FAN_ONLY: 5,
                            CONF_HVAC_MODE_AUTO: 6,
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
                            CONF_HVAC_MODE_OFF: 0,
                            CONF_HVAC_MODE_HEAT: 1,
                            CONF_HVAC_MODE_COOL: 2,
                            CONF_HVAC_MODE_HEAT_COOL: 3,
                            CONF_HVAC_MODE_DRY: 4,
                            CONF_HVAC_MODE_FAN_ONLY: 5,
                            CONF_HVAC_MODE_AUTO: 6,
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
                    CONF_MIN_TEMP: 23,
                    CONF_MAX_TEMP: 57,
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
                    CONF_MIN_TEMP: -57,
                    CONF_MAX_TEMP: -23,
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
    """Run configuration test for HVAC mode register."""
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
                    CONF_FAN_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_FAN_MODE_VALUES: {
                            CONF_FAN_MODE_ON: 0,
                            CONF_FAN_MODE_OFF: 1,
                            CONF_FAN_MODE_AUTO: 2,
                            CONF_FAN_MODE_LOW: 3,
                            CONF_FAN_MODE_MEDIUM: 4,
                            CONF_FAN_MODE_HIGH: 5,
                        },
                    },
                }
            ],
        },
    ],
)
async def test_config_fan_mode_register(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for Fan mode register."""
    state = hass.states.get(ENTITY_ID)
    assert FAN_ON in state.attributes[ATTR_FAN_MODES]
    assert FAN_OFF in state.attributes[ATTR_FAN_MODES]
    assert FAN_AUTO in state.attributes[ATTR_FAN_MODES]
    assert FAN_LOW in state.attributes[ATTR_FAN_MODES]
    assert FAN_MEDIUM in state.attributes[ATTR_FAN_MODES]
    assert FAN_HIGH in state.attributes[ATTR_FAN_MODES]
    assert FAN_TOP not in state.attributes[ATTR_FAN_MODES]
    assert FAN_MIDDLE not in state.attributes[ATTR_FAN_MODES]
    assert FAN_DIFFUSE not in state.attributes[ATTR_FAN_MODES]
    assert FAN_FOCUS not in state.attributes[ATTR_FAN_MODES]


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
                    CONF_SWING_MODE_REGISTER: {
                        CONF_ADDRESS: 11,
                        CONF_SWING_MODE_VALUES: {
                            CONF_SWING_MODE_SWING_ON: 0,
                            CONF_SWING_MODE_SWING_OFF: 1,
                            CONF_SWING_MODE_SWING_BOTH: 2,
                            CONF_SWING_MODE_SWING_HORIZ: 3,
                            CONF_SWING_MODE_SWING_VERT: 4,
                        },
                    },
                }
            ],
        },
    ],
)
async def test_config_swing_mode_register(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for Fan mode register."""
    state = hass.states.get(ENTITY_ID)
    assert SWING_ON in state.attributes[ATTR_SWING_MODES]
    assert SWING_OFF in state.attributes[ATTR_SWING_MODES]
    assert SWING_BOTH in state.attributes[ATTR_SWING_MODES]
    assert SWING_HORIZONTAL in state.attributes[ATTR_SWING_MODES]
    assert SWING_VERTICAL in state.attributes[ATTR_SWING_MODES]


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
            None,
            "unavailable",
        ),
    ],
)
async def test_temperature_error(hass: HomeAssistant, expected, mock_do_cycle) -> None:
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
                        CONF_TARGET_TEMP: [130, 131, 132, 133, 134, 135, 136],
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
                        CONF_TARGET_TEMP: 119,
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
                        CONF_TARGET_TEMP: 120,
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
    hass: HomeAssistant, mock_modbus_ha, result, register_words
) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(register_words)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == result


@pytest.mark.parametrize(
    ("do_config", "result", "register_words"),
    [
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_LOW: 0,
                                CONF_FAN_MODE_MEDIUM: 1,
                                CONF_FAN_MODE_HIGH: 2,
                            },
                        },
                    },
                ]
            },
            FAN_LOW,
            [0x00],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_LOW: 0,
                                CONF_FAN_MODE_MEDIUM: 1,
                                CONF_FAN_MODE_HIGH: 2,
                            },
                        },
                    },
                ]
            },
            FAN_MEDIUM,
            [0x01],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_LOW: 0,
                                CONF_FAN_MODE_MEDIUM: 1,
                                CONF_FAN_MODE_HIGH: 2,
                            },
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                    },
                ]
            },
            FAN_HIGH,
            [0x02],
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
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_LOW: 0,
                                CONF_FAN_MODE_MEDIUM: 1,
                                CONF_FAN_MODE_HIGH: 2,
                                CONF_FAN_MODE_TOP: 3,
                            },
                        },
                    },
                ]
            },
            FAN_TOP,
            [0x03],
        ),
    ],
)
async def test_service_climate_fan_update(
    hass: HomeAssistant, mock_modbus_ha, result, register_words
) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(register_words)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_FAN_MODE] == result


@pytest.mark.parametrize(
    ("do_config", "result", "register_words"),
    [
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_OFF: 0,
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_BOTH: 2,
                            },
                        },
                    },
                ]
            },
            SWING_BOTH,
            [0x02],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_OFF: 0,
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_VERT: 2,
                            },
                        },
                    },
                ]
            },
            SWING_ON,
            [0x01],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_OFF: 0,
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_HORIZ: 3,
                            },
                        },
                        CONF_HVAC_ONOFF_REGISTER: 119,
                    },
                ]
            },
            SWING_HORIZONTAL,
            [0x03],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_OFF: 0,
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_VERT: 2,
                                CONF_SWING_MODE_SWING_BOTH: 3,
                            },
                        },
                    },
                ]
            },
            SWING_OFF,
            [0x00],
        ),
        (
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 116,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_DATA_TYPE: DataType.INT32,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_OFF: 0,
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_VERT: 2,
                                CONF_SWING_MODE_SWING_BOTH: 3,
                            },
                        },
                    },
                ]
            },
            STATE_UNKNOWN,
            [0x05],
        ),
    ],
)
async def test_service_climate_swing_update(
    hass: HomeAssistant, mock_modbus_ha, result, register_words
) -> None:
    """Run test for service homeassistant.update_entity."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(register_words)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_SWING_MODE] == result


@pytest.mark.parametrize(
    ("temperature", "result", "do_config"),
    [
        (
            31,
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
            32,
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
            33.5,
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
            "34",
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
                        CONF_TARGET_TEMP: [150, 151, 152, 153, 154, 155, 156],
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
    hass: HomeAssistant, temperature, result, mock_modbus_ha
) -> None:
    """Test set_temperature."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(result)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
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
async def test_service_set_hvac_mode(
    hass: HomeAssistant, hvac_mode, result, mock_modbus_ha
) -> None:
    """Test set HVAC mode."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(result)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_HVAC_MODE: hvac_mode,
        },
        blocking=True,
    )


@pytest.mark.parametrize(
    ("fan_mode", "result", "do_config"),
    [
        (
            FAN_OFF,
            [0x02],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_ON: 1,
                                CONF_FAN_MODE_OFF: 2,
                            },
                        },
                    }
                ]
            },
        ),
        (
            FAN_ON,
            [0x01],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_FAN_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_FAN_MODE_VALUES: {
                                CONF_FAN_MODE_ON: 1,
                                CONF_FAN_MODE_OFF: 2,
                            },
                        },
                    }
                ]
            },
        ),
    ],
)
async def test_service_set_fan_mode(
    hass: HomeAssistant, fan_mode, result, mock_modbus_ha
) -> None:
    """Test set Fan mode."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(result)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_FAN_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_FAN_MODE: fan_mode,
        },
        blocking=True,
    )


@pytest.mark.parametrize(
    ("swing_mode", "result", "do_config"),
    [
        (
            SWING_OFF,
            [0x00],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: [118],
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_OFF: 0,
                            },
                        },
                    }
                ]
            },
        ),
        (
            SWING_ON,
            [0x01],
            {
                CONF_CLIMATES: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_TARGET_TEMP: 117,
                        CONF_ADDRESS: 117,
                        CONF_SLAVE: 10,
                        CONF_SWING_MODE_REGISTER: {
                            CONF_ADDRESS: 118,
                            CONF_SWING_MODE_VALUES: {
                                CONF_SWING_MODE_SWING_ON: 1,
                                CONF_SWING_MODE_SWING_OFF: 0,
                            },
                        },
                    }
                ]
            },
        ),
    ],
)
async def test_service_set_swing_mode(
    hass: HomeAssistant, swing_mode, result, mock_modbus_ha
) -> None:
    """Test set Swing mode."""
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(result)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_SWING_MODE: swing_mode,
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
        {CLIMATE_DOMAIN: {CONF_PLATFORM: MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert CLIMATE_DOMAIN in hass.config.components
