"""The tests for the Modbus light component."""

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.components.modbus.const import (
    CALL_TYPE_COIL,
    CALL_TYPE_DISCRETE,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_BRIGHTNESS_REGISTER,
    CONF_COLOR_TEMP_REGISTER,
    CONF_DEVICE_ADDRESS,
    CONF_INPUT_TYPE,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY,
    CONF_WRITE_TYPE,
    MODBUS_DOMAIN,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_ADDRESS,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_SCAN_INTERVAL,
    CONF_SLAVE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant, State
from homeassistant.setup import async_setup_component

from .conftest import TEST_ENTITY_NAME, ReadResult

ENTITY_ID = f"{LIGHT_DOMAIN}.{TEST_ENTITY_NAME}".replace(" ", "_")
ENTITY_ID2 = f"{ENTITY_ID}_2"


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_DEVICE_ADDRESS: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_REGISTER_HOLDING,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_REGISTER_INPUT,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: {
                        CONF_INPUT_TYPE: CALL_TYPE_DISCRETE,
                        CONF_ADDRESS: 1235,
                        CONF_STATE_OFF: 0,
                        CONF_STATE_ON: 1,
                    },
                }
            ]
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_COMMAND_OFF: 0x00,
                    CONF_COMMAND_ON: 0x01,
                    CONF_VERIFY: None,
                }
            ]
        },
    ],
)
async def test_config_light(hass: HomeAssistant, mock_modbus) -> None:
    """Run configuration test for light."""
    assert LIGHT_DOMAIN in hass.config.components


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                },
            ],
        },
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SLAVE: 1,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                },
            ],
        },
    ],
)
@pytest.mark.parametrize(
    ("register_words", "do_exception", "config_addon", "expected"),
    [
        (
            [0x00],
            False,
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            [0x01],
            False,
            {CONF_VERIFY: {}},
            STATE_ON,
        ),
        (
            [0xFE],
            False,
            {CONF_VERIFY: {}},
            STATE_OFF,
        ),
        (
            [0x00],
            True,
            {CONF_VERIFY: {}},
            STATE_UNAVAILABLE,
        ),
        (
            [0x00],
            True,
            None,
            STATE_OFF,
        ),
    ],
)
async def test_all_light(hass: HomeAssistant, mock_do_cycle, expected) -> None:
    """Run test for given config."""
    assert hass.states.get(ENTITY_ID).state == expected


@pytest.mark.parametrize(
    "mock_test_state",
    [
        (
            State(
                ENTITY_ID,
                STATE_ON,
                {
                    ATTR_BRIGHTNESS: 128,
                    ATTR_COLOR_TEMP_KELVIN: 4000,
                },
            ),
            State(
                ENTITY_ID2,
                STATE_ON,
                {},
            ),
        )
    ],
    indirect=True,
)
@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_BRIGHTNESS_REGISTER: 1,
                    CONF_COLOR_TEMP_REGISTER: 2,
                },
                {
                    CONF_NAME: f"{TEST_ENTITY_NAME} 2",
                    CONF_ADDRESS: 1235,
                    CONF_SCAN_INTERVAL: 0,
                },
            ]
        }
    ],
)
async def test_restore_state_light(
    hass: HomeAssistant, mock_test_state, mock_modbus
) -> None:
    """Test Modbus Light restore state with brightness and color_temp."""

    state_1 = hass.states.get(ENTITY_ID)
    state_2 = hass.states.get(ENTITY_ID2)

    assert state_1.state == STATE_ON
    assert state_1.attributes.get(ATTR_BRIGHTNESS) == mock_test_state[0].attributes.get(
        ATTR_BRIGHTNESS
    )
    assert state_1.attributes.get(ATTR_COLOR_TEMP_KELVIN) == mock_test_state[
        0
    ].attributes.get(ATTR_COLOR_TEMP_KELVIN)

    assert state_2.state == STATE_ON


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 17,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                },
                {
                    CONF_NAME: f"{TEST_ENTITY_NAME} 2",
                    CONF_ADDRESS: 18,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_VERIFY: {},
                },
            ],
        },
    ],
)
async def test_light_service_turn(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mock_modbus,
) -> None:
    """Run test for service turn_on/turn_off."""

    assert MODBUS_DOMAIN in hass.config.components
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, service_data={ATTR_ENTITY_ID: ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, service_data={ATTR_ENTITY_ID: ENTITY_ID}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    mock_modbus.read_holding_registers.return_value = ReadResult([0x01])
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, service_data={ATTR_ENTITY_ID: ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_ON
    mock_modbus.read_holding_registers.return_value = ReadResult([0x00])
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_OFF, service_data={ATTR_ENTITY_ID: ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_OFF

    mock_modbus.write_register.side_effect = ModbusException("fail write_")
    await hass.services.async_call(
        LIGHT_DOMAIN, SERVICE_TURN_ON, service_data={ATTR_ENTITY_ID: ENTITY_ID2}
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID2).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    (
        "do_config",
        "service_data",
        "expected_brightness",
        "expected_color_temp",
    ),
    [
        (
            {
                CONF_LIGHTS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                        CONF_SCAN_INTERVAL: 0,
                        CONF_BRIGHTNESS_REGISTER: 1,
                        CONF_COLOR_TEMP_REGISTER: 2,
                    }
                ]
            },
            {ATTR_BRIGHTNESS: 128, ATTR_COLOR_TEMP_KELVIN: 2000},
            50,
            0,
        ),
    ],
)
async def test_color_temp_brightness_light(
    hass: HomeAssistant,
    mock_modbus_ha,
    service_data,
    expected_brightness,
    expected_color_temp,
) -> None:
    """Test Modbus Light color temperature and brightness."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: ENTITY_ID, **service_data},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    calls = mock_modbus_ha.write_register.call_args_list

    assert any(
        call.args[0] == 1 and call.kwargs["value"] == expected_brightness
        for call in calls
    )
    assert any(
        call.args[0] == 2 and call.kwargs["value"] == expected_color_temp
        for call in calls
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    (
        "do_config",
        "brightness_input",
        "color_temp_input",
        "expected_brightness",
        "expected_color_temp",
    ),
    [
        (
            {
                CONF_LIGHTS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_BRIGHTNESS_REGISTER: 1,
                        CONF_COLOR_TEMP_REGISTER: 2,
                        CONF_WRITE_TYPE: CALL_TYPE_COIL,
                        CONF_VERIFY: {},
                    },
                ]
            },
            100,
            0,
            255,
            7000,
        ),
        (
            {
                CONF_LIGHTS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_BRIGHTNESS_REGISTER: 1,
                        CONF_WRITE_TYPE: CALL_TYPE_COIL,
                        CONF_VERIFY: {},
                    },
                ]
            },
            100,
            None,
            255,
            None,
        ),
        (
            {
                CONF_LIGHTS: [
                    {
                        CONF_NAME: TEST_ENTITY_NAME,
                        CONF_ADDRESS: 1234,
                        CONF_WRITE_TYPE: CALL_TYPE_COIL,
                        CONF_VERIFY: {},
                    },
                ]
            },
            None,
            None,
            None,
            None,
        ),
    ],
)
async def test_service_light_update(
    hass: HomeAssistant,
    mock_modbus_ha,
    brightness_input,
    color_temp_input,
    expected_brightness,
    expected_color_temp,
) -> None:
    """Run test for service homeassistant.update_entity."""
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_OFF
    mock_modbus_ha.read_coils.return_value = ReadResult([0x01])
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    mock_modbus_ha.read_holding_registers.return_value = ReadResult(
        [brightness_input, color_temp_input]
    )

    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
        },
        blocking=True,
    )
    if hass.states.get(ENTITY_ID).attributes.get(ATTR_BRIGHTNESS):
        assert (
            hass.states.get(ENTITY_ID).attributes.get(ATTR_BRIGHTNESS)
            == expected_brightness
        )
    if hass.states.get(ENTITY_ID).attributes.get(ATTR_COLOR_TEMP_KELVIN):
        assert (
            hass.states.get(ENTITY_ID).attributes.get(ATTR_COLOR_TEMP_KELVIN)
            == expected_color_temp
        )
    assert hass


async def test_no_discovery_info_light(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test setup without discovery info."""
    assert LIGHT_DOMAIN not in hass.config.components
    assert await async_setup_component(
        hass,
        LIGHT_DOMAIN,
        {LIGHT_DOMAIN: {CONF_PLATFORM: MODBUS_DOMAIN}},
    )
    await hass.async_block_till_done()
    assert LIGHT_DOMAIN in hass.config.components
