"""The tests for the Modbus water heater component."""

from typing import Any
from unittest import mock

import pytest

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.modbus.const import (
    CONF_CURRENT_TEMP_OFFSET,
    CONF_CURRENT_TEMP_SCALE,
    CONF_DATA_TYPE,
    CONF_DEVICE_ADDRESS,
    CONF_OFF_VALUE,
    CONF_ON_VALUE,
    CONF_ONOFF_COIL,
    CONF_ONOFF_REGISTER,
    CONF_OPERATION_MODE_ECO,
    CONF_OPERATION_MODE_ELECTRIC,
    CONF_OPERATION_MODE_HEAT_PUMP,
    CONF_OPERATION_MODE_OFF,
    CONF_OPERATION_MODE_PERFORMANCE,
    CONF_OPERATION_MODE_REGISTER,
    CONF_OPERATION_MODE_VALUES,
    CONF_SCALE,
    CONF_TARGET_TEMP,
    CONF_TARGET_TEMP_OFFSET,
    CONF_TARGET_TEMP_SCALE,
    CONF_TARGET_TEMP_WRITE_REGISTERS,
    CONF_WATER_HEATERS,
    CONF_WRITE_REGISTERS,
    DOMAIN,
    DataType,
)
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_OPERATION_LIST,
    ATTR_OPERATION_MODE,
    DOMAIN as WATER_HEATER_DOMAIN,
    SERVICE_SET_OPERATION_MODE,
    SERVICE_SET_TEMPERATURE,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_PERFORMANCE,
    WaterHeaterEntityFeature,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    CONF_ADDRESS,
    CONF_COUNT,
    CONF_NAME,
    CONF_OFFSET,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    CONF_STRUCTURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{WATER_HEATER_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")

CURRENT_TEMP_ADDRESS = 73
TARGET_TEMP_ADDRESS = 770
MODE_ADDRESS = 772
ONOFF_ADDRESS = 773

BASE_CONFIG = {
    CONF_NAME: TEST_ENTITY_NAME,
    CONF_ADDRESS: CURRENT_TEMP_ADDRESS,
    CONF_TARGET_TEMP: TARGET_TEMP_ADDRESS,
    CONF_SLAVE: 10,
    CONF_SCAN_INTERVAL: 0,
}
MODE_REGISTER_CONFIG = {
    CONF_ADDRESS: MODE_ADDRESS,
    CONF_OPERATION_MODE_VALUES: {
        CONF_OPERATION_MODE_HEAT_PUMP: 2,
        CONF_OPERATION_MODE_ECO: 9,
        CONF_OPERATION_MODE_PERFORMANCE: [10, 11],
        CONF_OPERATION_MODE_ELECTRIC: 12,
    },
}


def _registers(values: dict[int, list[int]]) -> Any:
    """Return a read side effect answering each address with its own registers."""

    async def read(address: int, **kwargs: Any) -> ReadResult:
        return ReadResult(values[address])

    return read


@pytest.mark.parametrize(
    "do_config",
    [
        {CONF_WATER_HEATERS: [BASE_CONFIG]},
        {
            CONF_WATER_HEATERS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: CURRENT_TEMP_ADDRESS,
                    CONF_TARGET_TEMP: TARGET_TEMP_ADDRESS,
                    CONF_DEVICE_ADDRESS: 10,
                }
            ]
        },
        {
            CONF_WATER_HEATERS: [
                {
                    **BASE_CONFIG,
                    CONF_DATA_TYPE: DataType.INT32,
                    CONF_TARGET_TEMP_WRITE_REGISTERS: True,
                    CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                    CONF_ON_VALUE: 5,
                    CONF_OFF_VALUE: 6,
                    CONF_WRITE_REGISTERS: True,
                    CONF_OPERATION_MODE_REGISTER: {
                        **MODE_REGISTER_CONFIG,
                        CONF_WRITE_REGISTERS: True,
                    },
                }
            ]
        },
    ],
)
@pytest.mark.usefixtures("mock_modbus")
async def test_config_water_heater(hass: HomeAssistant) -> None:
    """Run configuration test for water heater."""
    assert WATER_HEATER_DOMAIN in hass.config.components
    assert hass.states.get(ENTITY_ID) is not None


@pytest.mark.parametrize(
    ("do_config", "features", "operation_list"),
    [
        pytest.param(
            {CONF_WATER_HEATERS: [BASE_CONFIG]},
            WaterHeaterEntityFeature.TARGET_TEMPERATURE,
            None,
            id="temperature_only",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS},
                ]
            },
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.ON_OFF,
            None,
            id="onoff_coil",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE,
            [STATE_ECO, STATE_ELECTRIC, STATE_PERFORMANCE, STATE_HEAT_PUMP],
            id="operation_mode",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF,
            [
                STATE_ECO,
                STATE_ELECTRIC,
                STATE_PERFORMANCE,
                STATE_HEAT_PUMP,
                STATE_OFF,
            ],
            id="operation_mode_and_onoff",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: {
                            CONF_ADDRESS: MODE_ADDRESS,
                            CONF_OPERATION_MODE_VALUES: {
                                CONF_OPERATION_MODE_OFF: 0,
                                CONF_OPERATION_MODE_ECO: 1,
                            },
                        },
                    },
                ]
            },
            WaterHeaterEntityFeature.TARGET_TEMPERATURE
            | WaterHeaterEntityFeature.OPERATION_MODE
            | WaterHeaterEntityFeature.ON_OFF,
            [STATE_OFF, STATE_ECO],
            id="operation_mode_with_off",
        ),
    ],
)
@pytest.mark.usefixtures("mock_modbus")
async def test_config_features(
    hass: HomeAssistant,
    features: WaterHeaterEntityFeature,
    operation_list: list[str] | None,
) -> None:
    """Test the supported features and operation list built from the config."""
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == features
    assert state.attributes.get(ATTR_OPERATION_LIST) == operation_list


@pytest.mark.parametrize(
    ("do_config", "registers", "coils", "expected_state"),
    [
        pytest.param(
            {CONF_WATER_HEATERS: [BASE_CONFIG]},
            {},
            [],
            STATE_UNKNOWN,
            id="no_mode",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            {MODE_ADDRESS: [9]},
            [],
            STATE_ECO,
            id="mode",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            {MODE_ADDRESS: [11]},
            [],
            STATE_PERFORMANCE,
            id="mode_second_value",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            {MODE_ADDRESS: [99]},
            [],
            STATE_UNKNOWN,
            id="mode_unmapped",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            {MODE_ADDRESS: [2], ONOFF_ADDRESS: [1]},
            [],
            STATE_HEAT_PUMP,
            id="mode_onoff_register_on",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            {MODE_ADDRESS: [2], ONOFF_ADDRESS: [0]},
            [],
            STATE_OFF,
            id="mode_onoff_register_off",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OFF_VALUE: 6,
                    },
                ]
            },
            {ONOFF_ADDRESS: [6]},
            [],
            STATE_OFF,
            id="onoff_register_custom_off_value",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS},
                ]
            },
            {},
            [1],
            STATE_ON,
            id="onoff_coil_on",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS},
                ]
            },
            {},
            [0],
            STATE_OFF,
            id="onoff_coil_off",
        ),
    ],
)
async def test_update_state(
    hass: HomeAssistant,
    mock_modbus_ha: mock.AsyncMock,
    registers: dict[int, list[int]],
    coils: list[int],
    expected_state: str,
) -> None:
    """Test the state and temperatures read from the device."""
    mock_modbus_ha.read_holding_registers.side_effect = _registers(
        {CURRENT_TEMP_ADDRESS: [42], TARGET_TEMP_ADDRESS: [55], **registers}
    )
    mock_modbus_ha.read_coils.return_value = ReadResult(coils)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 42
    assert state.attributes[ATTR_TEMPERATURE] == 55


@pytest.mark.parametrize(
    ("do_config", "registers", "current", "target"),
    [
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_SCALE: 0.5, CONF_OFFSET: 10},
                ]
            },
            {CURRENT_TEMP_ADDRESS: [42], TARGET_TEMP_ADDRESS: [100]},
            31,
            60,
            id="common_scale_offset",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_CURRENT_TEMP_SCALE: 2,
                        CONF_CURRENT_TEMP_OFFSET: -10,
                        CONF_TARGET_TEMP_SCALE: 0.1,
                        CONF_TARGET_TEMP_OFFSET: 5,
                    },
                ]
            },
            {CURRENT_TEMP_ADDRESS: [21], TARGET_TEMP_ADDRESS: [550]},
            32,
            60,
            id="separate_scale_offset",
        ),
    ],
)
async def test_update_scale_and_offset(
    hass: HomeAssistant,
    mock_modbus_ha: mock.AsyncMock,
    registers: dict[int, list[int]],
    current: float,
    target: float,
) -> None:
    """Test scale and offset applied to the temperatures read."""
    mock_modbus_ha.read_holding_registers.side_effect = _registers(registers)
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == current
    assert state.attributes[ATTR_TEMPERATURE] == target


@pytest.mark.parametrize(
    "do_config",
    [
        {CONF_WATER_HEATERS: [BASE_CONFIG]},
        {
            CONF_WATER_HEATERS: [
                {
                    **BASE_CONFIG,
                    CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                },
            ]
        },
        {CONF_WATER_HEATERS: [{**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS}]},
        {CONF_WATER_HEATERS: [{**BASE_CONFIG, CONF_ONOFF_REGISTER: ONOFF_ADDRESS}]},
    ],
)
@pytest.mark.parametrize("do_exception", [True])
@pytest.mark.usefixtures("mock_modbus")
async def test_unavailable(hass: HomeAssistant) -> None:
    """Test the water heater is unavailable when the device does not answer."""
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("do_config", "temperature", "write_call", "expected_call"),
    [
        pytest.param(
            {CONF_WATER_HEATERS: [BASE_CONFIG]},
            50,
            "write_register",
            mock.call(TARGET_TEMP_ADDRESS, device_id=10, value=50),
            id="int16",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_TARGET_TEMP_WRITE_REGISTERS: True},
                ]
            },
            50,
            "write_registers",
            mock.call(TARGET_TEMP_ADDRESS, device_id=10, values=[50]),
            id="int16_write_registers",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_TARGET_TEMP_SCALE: 0.1,
                        CONF_TARGET_TEMP_OFFSET: 2,
                    },
                ]
            },
            50.3,
            "write_register",
            mock.call(TARGET_TEMP_ADDRESS, device_id=10, value=483),
            id="scale_offset_rounded",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_DATA_TYPE: DataType.INT32},
                ]
            },
            50,
            "write_registers",
            mock.call(TARGET_TEMP_ADDRESS, device_id=10, values=[0, 50]),
            id="int32",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_DATA_TYPE: DataType.FLOAT32},
                ]
            },
            50,
            "write_registers",
            mock.call(TARGET_TEMP_ADDRESS, device_id=10, values=[0x4248, 0x0000]),
            id="float32",
        ),
    ],
)
async def test_set_temperature(
    hass: HomeAssistant,
    mock_modbus_ha: mock.AsyncMock,
    temperature: float,
    write_call: str,
    expected_call: Any,
) -> None:
    """Test writing the target temperature."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_TEMPERATURE: temperature},
        blocking=True,
    )
    assert getattr(mock_modbus_ha, write_call).call_args_list == [expected_call]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_WATER_HEATERS: [
                {
                    **BASE_CONFIG,
                    CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                    CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                },
            ]
        },
    ],
)
async def test_set_temperature_with_operation_mode(
    hass: HomeAssistant, mock_modbus_ha: mock.AsyncMock
) -> None:
    """Test setting the target temperature together with the operation mode."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_TEMPERATURE: 50,
            ATTR_OPERATION_MODE: STATE_ECO,
        },
        blocking=True,
    )
    assert mock_modbus_ha.write_register.call_args_list == [
        mock.call(ONOFF_ADDRESS, device_id=10, value=1),
        mock.call(MODE_ADDRESS, device_id=10, value=9),
        mock.call(TARGET_TEMP_ADDRESS, device_id=10, value=50),
    ]


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_WATER_HEATERS: [
                {
                    **BASE_CONFIG,
                    CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                },
            ]
        },
    ],
)
async def test_set_temperature_with_invalid_operation_mode(
    hass: HomeAssistant, mock_modbus_ha: mock.AsyncMock
) -> None:
    """Test an unsupported operation mode is rejected before anything is written."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            WATER_HEATER_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_TEMPERATURE: 50,
                ATTR_OPERATION_MODE: STATE_GAS,
            },
            blocking=True,
        )
    mock_modbus_ha.write_register.assert_not_called()


@pytest.mark.parametrize(
    ("do_config", "operation_mode", "register_calls", "coil_calls"),
    [
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            STATE_ECO,
            [mock.call(MODE_ADDRESS, device_id=10, value=9)],
            [],
            id="mode",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            STATE_PERFORMANCE,
            [mock.call(MODE_ADDRESS, device_id=10, value=10)],
            [],
            id="mode_first_value",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            STATE_HEAT_PUMP,
            [
                mock.call(ONOFF_ADDRESS, device_id=10, value=1),
                mock.call(MODE_ADDRESS, device_id=10, value=2),
            ],
            [],
            id="mode_turns_on",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            STATE_OFF,
            [mock.call(ONOFF_ADDRESS, device_id=10, value=0)],
            [],
            id="off_by_onoff_register",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_COIL: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: MODE_REGISTER_CONFIG,
                    },
                ]
            },
            STATE_ELECTRIC,
            [mock.call(MODE_ADDRESS, device_id=10, value=12)],
            [mock.call(ONOFF_ADDRESS, device_id=10, value=1)],
            id="mode_turns_on_coil",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_OPERATION_MODE_REGISTER: {
                            CONF_ADDRESS: MODE_ADDRESS,
                            CONF_OPERATION_MODE_VALUES: {
                                CONF_OPERATION_MODE_OFF: 0,
                                CONF_OPERATION_MODE_ECO: 1,
                            },
                        },
                    },
                ]
            },
            STATE_OFF,
            [mock.call(ONOFF_ADDRESS, device_id=10, value=0)],
            [],
            id="off_keeps_mode_with_onoff",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: {
                            CONF_ADDRESS: MODE_ADDRESS,
                            CONF_OPERATION_MODE_VALUES: {
                                CONF_OPERATION_MODE_OFF: 0,
                                CONF_OPERATION_MODE_ECO: 1,
                            },
                        },
                    },
                ]
            },
            STATE_OFF,
            [mock.call(MODE_ADDRESS, device_id=10, value=0)],
            [],
            id="off_by_mode_register",
        ),
    ],
)
async def test_set_operation_mode(
    hass: HomeAssistant,
    mock_modbus_ha: mock.AsyncMock,
    operation_mode: str,
    register_calls: list[Any],
    coil_calls: list[Any],
) -> None:
    """Test writing the operation mode."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: operation_mode},
        blocking=True,
    )
    assert mock_modbus_ha.write_register.call_args_list == register_calls
    assert mock_modbus_ha.write_coil.call_args_list == coil_calls


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_WATER_HEATERS: [
                {
                    **BASE_CONFIG,
                    CONF_OPERATION_MODE_REGISTER: {
                        **MODE_REGISTER_CONFIG,
                        CONF_WRITE_REGISTERS: True,
                    },
                    CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                    CONF_WRITE_REGISTERS: True,
                },
            ]
        },
    ],
)
async def test_set_operation_mode_write_registers(
    hass: HomeAssistant, mock_modbus_ha: mock.AsyncMock
) -> None:
    """Test writing the operation mode with write multiple registers."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        SERVICE_SET_OPERATION_MODE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_OPERATION_MODE: STATE_ECO},
        blocking=True,
    )
    assert mock_modbus_ha.write_registers.call_args_list == [
        mock.call(ONOFF_ADDRESS, device_id=10, values=[1]),
        mock.call(MODE_ADDRESS, device_id=10, values=[9]),
    ]
    mock_modbus_ha.write_register.assert_not_called()


@pytest.mark.parametrize(
    ("do_config", "service", "write_call", "value"),
    [
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS},
                ]
            },
            SERVICE_TURN_ON,
            "write_coil",
            1,
            id="coil_on",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_ONOFF_COIL: ONOFF_ADDRESS},
                ]
            },
            SERVICE_TURN_OFF,
            "write_coil",
            0,
            id="coil_off",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_ON_VALUE: 5,
                        CONF_OFF_VALUE: 6,
                    },
                ]
            },
            SERVICE_TURN_ON,
            "write_register",
            5,
            id="register_on",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                        CONF_ON_VALUE: 5,
                        CONF_OFF_VALUE: 6,
                    },
                ]
            },
            SERVICE_TURN_OFF,
            "write_register",
            6,
            id="register_off",
        ),
    ],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    mock_modbus_ha: mock.AsyncMock,
    service: str,
    write_call: str,
    value: int,
) -> None:
    """Test turning the water heater on and off."""
    await hass.services.async_call(
        WATER_HEATER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    getattr(mock_modbus_ha, write_call).assert_called_once_with(
        ONOFF_ADDRESS, device_id=10, value=value
    )


@pytest.mark.parametrize(
    "do_config",
    [
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_ONOFF_COIL: ONOFF_ADDRESS,
                        CONF_ONOFF_REGISTER: ONOFF_ADDRESS,
                    },
                ]
            },
            id="coil_and_register",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: {
                            CONF_ADDRESS: MODE_ADDRESS,
                            CONF_OPERATION_MODE_VALUES: {
                                CONF_OPERATION_MODE_ECO: 1,
                                CONF_OPERATION_MODE_ELECTRIC: [2, 1],
                            },
                        },
                    },
                ]
            },
            id="duplicate_mode_value",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: {CONF_ADDRESS: MODE_ADDRESS},
                    },
                ]
            },
            id="mode_without_values",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_OPERATION_MODE_REGISTER: {
                            CONF_ADDRESS: MODE_ADDRESS,
                            CONF_OPERATION_MODE_VALUES: {CONF_OPERATION_MODE_ECO: []},
                        },
                    },
                ]
            },
            id="empty_mode_values",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_SCALE: 2, CONF_TARGET_TEMP_SCALE: 2},
                ]
            },
            id="conflicting_scale",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_TARGET_TEMP_SCALE: 0},
                ]
            },
            id="zero_scale",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {**BASE_CONFIG, CONF_DATA_TYPE: DataType.STRING, CONF_COUNT: 2},
                ]
            },
            id="string_data_type",
        ),
        pytest.param(
            {
                CONF_WATER_HEATERS: [
                    {
                        **BASE_CONFIG,
                        CONF_DATA_TYPE: DataType.CUSTOM,
                        CONF_STRUCTURE: ">i",
                        CONF_COUNT: 2,
                    },
                ]
            },
            id="custom_data_type",
        ),
    ],
)
@pytest.mark.usefixtures("mock_modbus_to_test_errors_config")
async def test_err_config_water_heater(hass: HomeAssistant) -> None:
    """Run a wrong configuration test for water heater."""
    assert WATER_HEATER_DOMAIN not in hass.config.components


async def test_no_discovery_info_water_heater(hass: HomeAssistant) -> None:
    """Test setup without discovery info."""
    assert WATER_HEATER_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        WATER_HEATER_DOMAIN,
        {WATER_HEATER_DOMAIN: {CONF_PLATFORM: DOMAIN}},
    )
    await hass.async_block_till_done()
    assert WATER_HEATER_DOMAIN in hass.config.components
