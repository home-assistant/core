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
    LIGHT_DEFAULT_MAX_KELVIN,
    LIGHT_DEFAULT_MIN_KELVIN,
    LIGHT_MODBUS_SCALE_MAX,
    LIGHT_MODBUS_SCALE_MIN,
    MODBUS_DOMAIN,
)
from homeassistant.components.modbus.light import ModbusLight
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
    [(State(ENTITY_ID, STATE_ON),)],
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
                }
            ]
        },
    ],
)
async def test_restore_state_light(
    hass: HomeAssistant, mock_test_state, mock_modbus
) -> None:
    """Run test for sensor restore state."""
    assert hass.states.get(ENTITY_ID).state == mock_test_state[0].state


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
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_BRIGHTNESS_REGISTER: 1,
                    CONF_COLOR_TEMP_REGISTER: 2,
                    CONF_WRITE_TYPE: CALL_TYPE_COIL,
                    CONF_VERIFY: {},
                }
            ]
        },
    ],
)
async def test_service_light_update(hass: HomeAssistant, mock_modbus_ha) -> None:
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
    mock_modbus_ha.read_holding_registers.return_value = ReadResult([100, 0])
    expected_brightness = 255
    expected_color_temp = 7000
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {
            ATTR_ENTITY_ID: ENTITY_ID,
        },
        blocking=True,
    )
    assert (
        hass.states.get(ENTITY_ID).attributes.get(ATTR_BRIGHTNESS)
        == expected_brightness
    )
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


@pytest.mark.parametrize(
    "do_config",
    [
        {
            CONF_LIGHTS: [
                {
                    CONF_NAME: TEST_ENTITY_NAME,
                    CONF_ADDRESS: 1234,
                    CONF_WRITE_TYPE: CALL_TYPE_REGISTER_HOLDING,
                    CONF_SCAN_INTERVAL: 0,
                    CONF_BRIGHTNESS_REGISTER: 1,
                }
            ]
        }
    ],
)
async def test_brightness_light(hass: HomeAssistant, mock_modbus_ha) -> None:
    """Test Modbus Light brightness."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS: 128,
        },
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON
    brightness = 128
    calls = mock_modbus_ha.write_register.call_args_list
    modbus_brightness = ModbusLight._convert_brightness_to_modbus(brightness)

    assert any(
        call.args[0] == 1 and call.kwargs["value"] == modbus_brightness
        for call in calls
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


@pytest.mark.parametrize(
    "do_config",
    [
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
        }
    ],
)
async def test_color_temp_light(hass: HomeAssistant, mock_modbus_ha) -> None:
    """Test Modbus Light color temperature."""
    assert hass.states.get(ENTITY_ID).state == STATE_OFF

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_ON,
        service_data={
            ATTR_ENTITY_ID: ENTITY_ID,
            ATTR_BRIGHTNESS: 128,
            ATTR_COLOR_TEMP_KELVIN: 2000,
        },
        blocking=True,
    )

    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_ON

    calls = mock_modbus_ha.write_register.call_args_list
    brightness = 128
    modbus_brightness = ModbusLight._convert_brightness_to_modbus(brightness)
    color_temp = 2000
    modbus_temp = round(
        LIGHT_MODBUS_SCALE_MIN
        + (color_temp - LIGHT_DEFAULT_MIN_KELVIN)
        * (LIGHT_MODBUS_SCALE_MAX - LIGHT_MODBUS_SCALE_MIN)
        / (LIGHT_DEFAULT_MAX_KELVIN - LIGHT_DEFAULT_MIN_KELVIN)
    )

    assert any(
        call.args[0] == 1 and call.kwargs["value"] == modbus_brightness
        for call in calls
    )
    assert any(
        call.args[0] == 2 and call.kwargs["value"] == modbus_temp for call in calls
    )

    await hass.services.async_call(
        LIGHT_DOMAIN,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_OFF


CONFIG_LIGHT = {
    CONF_NAME: TEST_ENTITY_NAME,
    CONF_ADDRESS: 1234,
    CONF_SLAVE: 1,
    CONF_COMMAND_OFF: 0x00,
    CONF_COMMAND_ON: 0x01,
    CONF_WRITE_TYPE: CALL_TYPE_COIL,
    CONF_SCAN_INTERVAL: 0,
    CONF_BRIGHTNESS_REGISTER: 1,
    CONF_COLOR_TEMP_REGISTER: 2,
}


@pytest.mark.asyncio
class TestModbusConvectors:
    """Tests for ModbusLight brightness and color temperature conversions."""

    light = ModbusLight(None, None, CONFIG_LIGHT)

    async def test_convert_brightness_to_modbus(self):
        """Test conversion of brightness (0–255) to Modbus scale (0–100)."""
        brightness = 128
        expected = 50
        result = self.light._convert_brightness_to_modbus(brightness)
        assert result == expected
        result = self.light._convert_brightness_to_modbus("invalid")
        assert result is None

    async def test_convert_color_temp_to_modbus(self):
        """Test conversion of color temperature in Kelvin to Modbus scale (0–100)."""
        kelvin = 2000
        expected = 0

        result = self.light._convert_color_temp_to_modbus(kelvin)
        assert result == expected
        result = self.light._convert_color_temp_to_modbus(None)
        assert result is None
        result = self.light._convert_color_temp_to_modbus("invalid")
        assert result is None

    async def test_percent_to_temperature(self):
        """Test conversion of Modbus percentage (0–100) to color temperature in Kelvin."""
        percent = 20
        expected_kelvin = 3000

        result = self.light._convert_modbus_percent_to_temperature(percent)
        assert result == expected_kelvin
        result = self.light._convert_modbus_percent_to_temperature(None)
        assert result is None
        result = self.light._convert_modbus_percent_to_temperature("invalid")
        assert result is None

        self.light._attr_min_color_temp_kelvin = None
        self.light._attr_max_color_temp_kelvin = None

        result = self.light._convert_modbus_percent_to_temperature(20)
        assert result is None

        result = self.light._convert_color_temp_to_modbus(3000)
        assert result is None

    async def test_percent_to_brightness(self):
        """Test conversion of Modbus percentage (0–100) to brightness (0–255)."""
        percent = 20
        expected_brightness = 51

        result = self.light._convert_modbus_percent_to_brightness(percent)
        assert result == expected_brightness
        result = self.light._convert_modbus_percent_to_brightness(None)
        assert result is None
        result = self.light._convert_modbus_percent_to_brightness("invalid")
        assert result is None

    async def test_color_temp_bounds(self):
        """Test color temp bounds with None."""
        self.light._attr_min_color_temp_kelvin = None
        self.light._attr_max_color_temp_kelvin = None

        result = self.light._convert_modbus_percent_to_temperature(20)
        assert result is None
        result = self.light._convert_color_temp_to_modbus(3000)
        assert result is None
