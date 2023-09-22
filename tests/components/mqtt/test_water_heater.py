"""The tests for the mqtt water heater component."""
import copy
import json
from typing import Any
from unittest.mock import call, patch

import pytest
import voluptuous as vol

from homeassistant.components import mqtt, water_heater
from homeassistant.components.mqtt.water_heater import (
    MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED,
)
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_OPERATION_MODE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    STATE_ECO,
    STATE_ELECTRIC,
    STATE_GAS,
    STATE_HEAT_PUMP,
    STATE_HIGH_DEMAND,
    STATE_PERFORMANCE,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_conversion import TemperatureConverter

from .test_common import (
    help_custom_config,
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_encoding_subscribable_topics,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_publishing_with_custom_encoding,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_skipped_async_ha_write_state,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.water_heater import common
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

ENTITY_WATER_HEATER = "water_heater.test"


_DEFAULT_MIN_TEMP_CELSIUS = round(
    TemperatureConverter.convert(
        DEFAULT_MIN_TEMP,
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.CELSIUS,
    ),
    1,
)
_DEFAULT_MAX_TEMP_CELSIUS = round(
    TemperatureConverter.convert(
        DEFAULT_MAX_TEMP,
        UnitOfTemperature.FAHRENHEIT,
        UnitOfTemperature.CELSIUS,
    ),
    1,
)


DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        water_heater.DOMAIN: {
            "name": "test",
            "mode_command_topic": "mode-topic",
            "temperature_command_topic": "temperature-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def water_heater_platform_only():
    """Only setup the water heater platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.WATER_HEATER]):
        yield


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_setup_params(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the initial parameters."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)

    assert state.attributes.get("temperature") == _DEFAULT_MIN_TEMP_CELSIUS
    assert state.state == "off"
    # default water heater min/max temp in celsius
    assert state.attributes.get("min_temp") == _DEFAULT_MIN_TEMP_CELSIUS
    assert state.attributes.get("max_temp") == _DEFAULT_MAX_TEMP_CELSIUS


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_supported_features(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the supported_features."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    support = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    assert state.attributes.get("supported_features") == support


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_get_operation_modes(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that the operation list returns the correct modes."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert [
        STATE_ECO,
        STATE_ELECTRIC,
        STATE_GAS,
        STATE_HEAT_PUMP,
        STATE_HIGH_DEMAND,
        STATE_PERFORMANCE,
        STATE_OFF,
    ] == state.attributes.get("operation_list")


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_set_operation_mode_bad_attr_and_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setting operation mode without required attribute."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_operation_mode(hass, None, ENTITY_WATER_HEATER)
    assert "string value is None for dictionary value @ data['operation_mode']" in str(
        excinfo.value
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_set_operation(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting of new operation mode."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    await common.async_set_operation_mode(hass, "eco", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "eco"
    mqtt_mock.async_publish.assert_called_once_with("mode-topic", "eco", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"mode_state_topic": "mode-state"},),
        )
    ],
)
async def test_set_operation_pessimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting operation mode in pessimistic mode."""
    await hass.async_block_till_done()
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "unknown"

    await common.async_set_operation_mode(hass, "eco", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "unknown"

    async_fire_mqtt_message(hass, "mode-state", "eco")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "eco"

    async_fire_mqtt_message(hass, "mode-state", "bogus mode")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "eco"


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "mode_state_topic": "mode-state",
                    "optimistic": True,
                },
            ),
        )
    ],
)
async def test_set_operation_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting operation mode in optimistic mode."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"

    await common.async_set_operation_mode(hass, "electric", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "electric"

    async_fire_mqtt_message(hass, "mode-state", "performance")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "performance"

    async_fire_mqtt_message(hass, "mode-state", "bogus mode")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "performance"


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"power_command_topic": "power-command"},),
        )
    ],
)
async def test_set_operation_with_power_command(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting of new operation mode with power command enabled."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    await common.async_set_operation_mode(hass, "electric", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "electric"
    mqtt_mock.async_publish.assert_has_calls([call("mode-topic", "electric", 0, False)])
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_operation_mode(hass, "off", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    mqtt_mock.async_publish.assert_has_calls([call("mode-topic", "off", 0, False)])
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, ENTITY_WATER_HEATER)
    # the water heater is not updated optimistically as this is not supported
    mqtt_mock.async_publish.assert_has_calls([call("power-command", "ON", 0, False)])
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, ENTITY_WATER_HEATER)
    mqtt_mock.async_publish.assert_has_calls([call("power-command", "OFF", 0, False)])
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"power_command_topic": "power-command", "optimistic": True},),
        )
    ],
)
async def test_turn_on_and_off_optimistic_with_power_command(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting of turn on/off with power command enabled."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    await common.async_set_operation_mode(hass, "electric", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "electric"
    mqtt_mock.async_publish.assert_has_calls([call("mode-topic", "electric", 0, False)])
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_operation_mode(hass, "off", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"

    await common.async_turn_on(hass, ENTITY_WATER_HEATER)
    # the water heater is not updated optimistically as this is not supported
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "off"
    mqtt_mock.async_publish.assert_has_calls([call("power-command", "ON", 0, False)])
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_operation_mode(hass, "gas", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "gas"
    await common.async_turn_off(hass, ENTITY_WATER_HEATER)
    # the water heater is not updated optimistically as this is not supported
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "gas"
    mqtt_mock.async_publish.assert_has_calls([call("power-command", "OFF", 0, False)])
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_set_target_temperature(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting the target temperature."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == _DEFAULT_MIN_TEMP_CELSIUS
    await common.async_set_operation_mode(hass, "performance", ENTITY_WATER_HEATER)
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "performance"
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-topic", "performance", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(
        hass, temperature=50, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 50
    mqtt_mock.async_publish.assert_called_once_with(
        "temperature-topic", "50.0", 0, False
    )

    # also test directly supplying the operation mode to set_temperature
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(
        hass, temperature=47, operation_mode="eco", entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "eco"
    assert state.attributes.get("temperature") == 47
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("mode-topic", "eco", 0, False),
            call("temperature-topic", "47.0", 0, False),
        ]
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"temperature_state_topic": "temperature-state"},),
        )
    ],
)
async def test_set_target_temperature_pessimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting the target temperature."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") is None
    await common.async_set_operation_mode(hass, "performance", ENTITY_WATER_HEATER)
    await common.async_set_temperature(
        hass, temperature=60, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") is None

    async_fire_mqtt_message(hass, "temperature-state", "1701")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 1701

    async_fire_mqtt_message(hass, "temperature-state", "not a number")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 1701


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"temperature_state_topic": "temperature-state", "optimistic": True},),
        )
    ],
)
async def test_set_target_temperature_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting the target temperature optimistic."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == _DEFAULT_MIN_TEMP_CELSIUS
    await common.async_set_operation_mode(hass, "performance", ENTITY_WATER_HEATER)
    await common.async_set_temperature(
        hass, temperature=55, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 55

    async_fire_mqtt_message(hass, "temperature-state", "49")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 49

    async_fire_mqtt_message(hass, "temperature-state", "not a number")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 49


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            ({"current_temperature_topic": "current_temperature"},),
        )
    ],
)
async def test_receive_mqtt_temperature(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting the current temperature via MQTT."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "current_temperature", "53")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("current_temperature") == 53

    async_fire_mqtt_message(hass, "current_temperature", "")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert (
        "Invalid empty payload for attribute _attr_current_temperature, ignoring update"
        in caplog.text
    )
    assert state.attributes.get("current_temperature") == 53


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, water_heater.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                water_heater.DOMAIN: {
                    "name": "test",
                    "mode_command_topic": "mode-topic",
                    "temperature_command_topic": "temperature-topic",
                    # By default, just unquote the JSON-strings
                    "value_template": "{{ value_json }}",
                    "mode_state_template": "{{ value_json.attribute }}",
                    "temperature_state_template": "{{ value_json }}",
                    "current_temperature_template": "{{ value_json}}",
                    "mode_state_topic": "mode-state",
                    "temperature_state_topic": "temperature-state",
                    "current_temperature_topic": "current-temperature",
                }
            }
        }
    ],
)
async def test_get_with_templates(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test getting various attributes with templates."""
    await mqtt_mock_entry()

    # Operation Mode
    state = hass.states.get(ENTITY_WATER_HEATER)
    async_fire_mqtt_message(hass, "mode-state", '{"attribute": "eco"}')
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "eco"

    # Temperature - with valid value
    assert state.attributes.get("temperature") is None
    async_fire_mqtt_message(hass, "temperature-state", '"1031"')
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 1031

    # Temperature - with invalid value
    async_fire_mqtt_message(hass, "temperature-state", '"-INVALID-"')
    state = hass.states.get(ENTITY_WATER_HEATER)
    # make sure, the invalid value gets logged...
    assert "Could not parse temperature_state_template from -INVALID-" in caplog.text
    # ... but the actual value stays unchanged.
    assert state.attributes.get("temperature") == 1031

    # Temperature - with JSON null value
    async_fire_mqtt_message(hass, "temperature-state", "null")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") is None

    # Current temperature
    async_fire_mqtt_message(hass, "current-temperature", '"74656"')
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("current_temperature") == 74656
    # Test resetting the current temperature using a JSON null value
    async_fire_mqtt_message(hass, "current-temperature", "null")
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("current_temperature") is None


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                water_heater.DOMAIN: {
                    "name": "test",
                    "mode_command_topic": "mode-topic",
                    "temperature_command_topic": "temperature-topic",
                    "power_command_topic": "power-topic",
                    # Create simple templates
                    "mode_command_template": "mode: {{ value }}",
                    "temperature_command_template": "temp: {{ value }}",
                    "power_command_template": "pwr: {{ value }}",
                }
            }
        }
    ],
)
async def test_set_and_templates(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test setting various attributes with templates."""
    mqtt_mock = await mqtt_mock_entry()

    # Mode
    await common.async_set_operation_mode(hass, "heat_pump", ENTITY_WATER_HEATER)
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-topic", "mode: heat_pump", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.state == "heat_pump"

    # Temperature
    await common.async_set_temperature(
        hass, temperature=107, entity_id=ENTITY_WATER_HEATER
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "temperature-topic", "temp: 107.0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 107

    # Power
    await common.async_turn_on(hass, entity_id=ENTITY_WATER_HEATER)
    mqtt_mock.async_publish.assert_called_once_with("power-topic", "pwr: ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    await common.async_turn_off(hass, entity_id=ENTITY_WATER_HEATER)
    mqtt_mock.async_publish.assert_called_once_with("power-topic", "pwr: OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [help_custom_config(water_heater.DOMAIN, DEFAULT_CONFIG, ({"min_temp": 70},))],
)
async def test_min_temp_custom(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test a custom min temp."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    min_temp = state.attributes.get("min_temp")

    assert isinstance(min_temp, float)
    assert state.attributes.get("min_temp") == 70


@pytest.mark.parametrize(
    "hass_config",
    [help_custom_config(water_heater.DOMAIN, DEFAULT_CONFIG, ({"max_temp": 220},))],
)
async def test_max_temp_custom(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test a custom max temp."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    max_temp = state.attributes.get("max_temp")

    assert isinstance(max_temp, float)
    assert max_temp == 220


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "temperature_unit": "F",
                    "current_temperature_topic": "current_temperature",
                },
            ),
        )
    ],
)
async def test_temperature_unit(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that setting temperature unit converts temperature values."""
    await mqtt_mock_entry()

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == _DEFAULT_MIN_TEMP_CELSIUS
    assert state.attributes.get("min_temp") == _DEFAULT_MIN_TEMP_CELSIUS
    assert state.attributes.get("max_temp") == _DEFAULT_MAX_TEMP_CELSIUS

    async_fire_mqtt_message(hass, "current_temperature", "127")

    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("current_temperature") == 52.8


@pytest.mark.parametrize(
    ("hass_config", "temperature_unit", "initial", "min_temp", "max_temp", "current"),
    [
        (
            help_custom_config(
                water_heater.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "temperature_unit": "F",
                        "current_temperature_topic": "current_temperature",
                    },
                ),
            ),
            UnitOfTemperature.CELSIUS,
            _DEFAULT_MIN_TEMP_CELSIUS,
            _DEFAULT_MIN_TEMP_CELSIUS,
            _DEFAULT_MAX_TEMP_CELSIUS,
            48.9,
        ),
        (
            help_custom_config(
                water_heater.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "temperature_unit": "F",
                        "current_temperature_topic": "current_temperature",
                    },
                ),
            ),
            UnitOfTemperature.KELVIN,
            316,
            316,
            333,
            322,
        ),
        (
            help_custom_config(
                water_heater.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "temperature_unit": "F",
                        "current_temperature_topic": "current_temperature",
                    },
                ),
            ),
            UnitOfTemperature.FAHRENHEIT,
            DEFAULT_MIN_TEMP,
            DEFAULT_MIN_TEMP,
            DEFAULT_MAX_TEMP,
            120,
        ),
    ],
)
async def test_alt_temperature_unit(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    temperature_unit: UnitOfTemperature,
    initial: float,
    min_temp: float,
    max_temp: float,
    current: float,
) -> None:
    """Test deriving the systems temperature unit."""
    with patch.object(hass.config.units, "temperature_unit", temperature_unit):
        await mqtt_mock_entry()

        state = hass.states.get(ENTITY_WATER_HEATER)
        assert state.attributes.get("temperature") == initial
        assert state.attributes.get("min_temp") == min_temp
        assert state.attributes.get("max_temp") == max_temp

        async_fire_mqtt_message(hass, "current_temperature", "120")

        state = hass.states.get(ENTITY_WATER_HEATER)
        assert state.attributes.get("current_temperature") == current


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        water_heater.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_WATER_HEATER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry,
        caplog,
        water_heater.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry,
        caplog,
        water_heater.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry,
        caplog,
        water_heater.DOMAIN,
        DEFAULT_CONFIG,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                water_heater.DOMAIN: [
                    {
                        "name": "Test 1",
                        "mode_state_topic": "test_topic1/state",
                        "mode_command_topic": "test_topic1/command",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "mode_state_topic": "test_topic2/state",
                        "mode_command_topic": "test_topic2/command",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one water heater per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, water_heater.DOMAIN)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("current_temperature_topic", "22.1", ATTR_CURRENT_TEMPERATURE, 22.1),
        ("mode_state_topic", "eco", ATTR_OPERATION_MODE, None),
        ("temperature_state_topic", "19.9", ATTR_TEMPERATURE, 19.9),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str | None,
    attribute_value: Any,
) -> None:
    """Test handling of incoming encoded payload."""
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][water_heater.DOMAIN])
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        water_heater.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
    )


async def test_discovery_removal_water_heater(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered water heater."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][water_heater.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry, caplog, water_heater.DOMAIN, data
    )


async def test_discovery_update_water_heater(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered water heater."""
    config1 = {"name": "Beer"}
    config2 = {"name": "Milk"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry, caplog, water_heater.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_water_heater(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered water heater."""
    data1 = '{ "name": "Beer" }'
    with patch(
        "homeassistant.components.mqtt.water_heater.MqttWaterHeater.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            caplog,
            water_heater.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "mode_command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "mode_command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, water_heater.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT water heater device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT water heater device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        mqtt.DOMAIN: {
            water_heater.DOMAIN: {
                "name": "test",
                "mode_state_topic": "test-topic",
                "availability_topic": "avty-topic",
            }
        }
    }
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock_entry,
        water_heater.DOMAIN,
        config,
        ["test-topic", "avty-topic"],
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, water_heater.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    config = {
        mqtt.DOMAIN: {
            water_heater.DOMAIN: {
                "name": "test",
                "mode_command_topic": "command-topic",
                "mode_state_topic": "test-topic",
            }
        }
    }
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        water_heater.DOMAIN,
        config,
        water_heater.SERVICE_SET_OPERATION_MODE,
        command_topic="command-topic",
        command_payload="eco",
        state_topic="test-topic",
        service_parameters={"operation_mode": "eco"},
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_precision_default(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that setting precision to tenths works as intended."""
    mqtt_mock = await mqtt_mock_entry()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 23.7
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [help_custom_config(water_heater.DOMAIN, DEFAULT_CONFIG, ({"precision": 0.5},))],
)
async def test_precision_halves(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that setting precision to halves works as intended."""
    mqtt_mock = await mqtt_mock_entry()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 23.5
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [help_custom_config(water_heater.DOMAIN, DEFAULT_CONFIG, ({"precision": 1.0},))],
)
async def test_precision_whole(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that setting precision to whole works as intended."""
    mqtt_mock = await mqtt_mock_entry()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_WATER_HEATER
    )
    state = hass.states.get(ENTITY_WATER_HEATER)
    assert state.attributes.get("temperature") == 24.0
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            water_heater.SERVICE_SET_OPERATION_MODE,
            "mode_command_topic",
            {"operation_mode": "electric"},
            "electric",
            "mode_command_template",
        ),
        (
            water_heater.SERVICE_SET_TEMPERATURE,
            "temperature_command_topic",
            {"temperature": "20.1"},
            20.1,
            "temperature_command_template",
        ),
        (
            water_heater.SERVICE_TURN_ON,
            "power_command_topic",
            {},
            "ON",
            "power_command_template",
        ),
        (
            water_heater.SERVICE_TURN_OFF,
            "power_command_topic",
            {},
            "OFF",
            "power_command_template",
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = water_heater.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test reloading the MQTT platform."""
    domain = water_heater.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    "hass_config",
    [DEFAULT_CONFIG, {"mqtt": [DEFAULT_CONFIG["mqtt"]]}],
    ids=["platform_key", "listed"],
)
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = water_heater.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = water_heater.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            water_heater.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "mode_state_topic": "mode-state-topic",
                    "current_temperature_topic": "current-temperature-topic",
                    "temperature_state_topic": "temperature-state-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
        ("mode-state-topic", "gas", "electric"),
        ("current-temperature-topic", "18.0", "18.1"),
        ("temperature-state-topic", "18", "19"),
    ],
)
async def test_skipped_async_ha_write_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    payload1: str,
    payload2: str,
) -> None:
    """Test a write state command is only called when there is change."""
    await mqtt_mock_entry()
    await help_test_skipped_async_ha_write_state(hass, topic, payload1, payload2)
