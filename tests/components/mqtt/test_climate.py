"""The tests for the mqtt climate component."""
import copy
import json
from unittest.mock import call, patch

import pytest
import voluptuous as vol

from homeassistant.components import climate
from homeassistant.components.climate import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.components.climate.const import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    CURRENT_HVAC_ACTIONS,
    DOMAIN as CLIMATE_DOMAIN,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.mqtt.climate import MQTT_CLIMATE_ATTRIBUTES_BLOCKED
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.setup import async_setup_component

from .test_common import (
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
    help_test_reloadable_late,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.climate import common

ENTITY_CLIMATE = "climate.test"

DEFAULT_CONFIG = {
    CLIMATE_DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "mode_command_topic": "mode-topic",
        "temperature_command_topic": "temperature-topic",
        "temperature_low_command_topic": "temperature-low-topic",
        "temperature_high_command_topic": "temperature-high-topic",
        "fan_mode_command_topic": "fan-mode-topic",
        "swing_mode_command_topic": "swing-mode-topic",
        "aux_command_topic": "aux-topic",
        "preset_mode_command_topic": "preset-mode-topic",
        "preset_modes": [
            "eco",
            "away",
            "boost",
            "comfort",
            "home",
            "sleep",
            "activity",
        ],
    }
}


@pytest.fixture(autouse=True)
def climate_platform_only():
    """Only setup the climate platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.CLIMATE]):
        yield


async def test_setup_params(hass, mqtt_mock_entry_with_yaml_config):
    """Test the initial parameters."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 21
    assert state.attributes.get("fan_mode") == "low"
    assert state.attributes.get("swing_mode") == "off"
    assert state.state == "off"
    assert state.attributes.get("min_temp") == DEFAULT_MIN_TEMP
    assert state.attributes.get("max_temp") == DEFAULT_MAX_TEMP


async def test_preset_none_in_preset_modes(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test the preset mode payload reset configuration."""
    config = copy.deepcopy(DEFAULT_CONFIG[CLIMATE_DOMAIN])
    config["preset_modes"].append("none")
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {CLIMATE_DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()
    assert "Invalid config for [climate.mqtt]: not a valid value" in caplog.text
    state = hass.states.get(ENTITY_CLIMATE)
    assert state is None


# AWAY and HOLD mode topics and templates are deprecated, support will be removed with release 2022.9
@pytest.mark.parametrize(
    "parameter,config_value",
    [
        ("away_mode_command_topic", "away-mode-command-topic"),
        ("away_mode_state_topic", "away-mode-state-topic"),
        ("away_mode_state_template", "{{ value_json }}"),
        ("hold_mode_command_topic", "hold-mode-command-topic"),
        ("hold_mode_command_template", "hold-mode-command-template"),
        ("hold_mode_state_topic", "hold-mode-state-topic"),
        ("hold_mode_state_template", "{{ value_json }}"),
    ],
)
async def test_preset_modes_deprecation_guard(
    hass, mqtt_mock_entry_no_yaml_config, caplog, parameter, config_value
):
    """Test the configuration for invalid legacy parameters."""
    config = copy.deepcopy(DEFAULT_CONFIG[CLIMATE_DOMAIN])
    config[parameter] = config_value
    assert await async_setup_component(hass, CLIMATE_DOMAIN, {CLIMATE_DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state is None


async def test_supported_features(hass, mqtt_mock_entry_with_yaml_config):
    """Test the supported_features."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    support = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.SWING_MODE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.AUX_HEAT
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )

    assert state.attributes.get("supported_features") == support


async def test_get_hvac_modes(hass, mqtt_mock_entry_with_yaml_config):
    """Test that the operation list returns the correct modes."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    modes = state.attributes.get("hvac_modes")
    assert [
        HVACMode.AUTO,
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.HEAT,
        HVACMode.DRY,
        HVACMode.FAN_ONLY,
    ] == modes


async def test_set_operation_bad_attr_and_state(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test setting operation mode without required attribute.

    Also check the state.
    """
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "off"
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_hvac_mode(hass, None, ENTITY_CLIMATE)
    assert (
        "expected HVACMode or one of 'off', 'heat', 'cool', 'heat_cool', 'auto', 'dry', 'fan_only' for dictionary value @ data['hvac_mode']"
    ) in str(excinfo.value)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "off"


async def test_set_operation(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of new operation mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "off"
    await common.async_set_hvac_mode(hass, "cool", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"
    assert state.state == "cool"
    mqtt_mock.async_publish.assert_called_once_with("mode-topic", "cool", 0, False)


async def test_set_operation_pessimistic(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting operation mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["mode_state_topic"] = "mode-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "unknown"

    await common.async_set_hvac_mode(hass, "cool", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "unknown"

    async_fire_mqtt_message(hass, "mode-state", "cool")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"

    async_fire_mqtt_message(hass, "mode-state", "bogus mode")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"


async def test_set_operation_with_power_command(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of new operation mode with power command enabled."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["power_command_topic"] = "power-command"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "off"
    await common.async_set_hvac_mode(hass, "cool", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"
    mqtt_mock.async_publish.assert_has_calls(
        [call("power-command", "ON", 0, False), call("mode-topic", "cool", 0, False)]
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_hvac_mode(hass, "off", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "off"
    mqtt_mock.async_publish.assert_has_calls(
        [call("power-command", "OFF", 0, False), call("mode-topic", "off", 0, False)]
    )
    mqtt_mock.async_publish.reset_mock()


async def test_set_fan_mode_bad_attr(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test setting fan mode without required attribute."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "low"
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_fan_mode(hass, None, ENTITY_CLIMATE)
    assert "string value is None for dictionary value @ data['fan_mode']" in str(
        excinfo.value
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "low"


async def test_set_fan_mode_pessimistic(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of new fan mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["fan_mode_state_topic"] = "fan-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") is None

    await common.async_set_fan_mode(hass, "high", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") is None

    async_fire_mqtt_message(hass, "fan-state", "high")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "high"

    async_fire_mqtt_message(hass, "fan-state", "bogus mode")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "high"


async def test_set_fan_mode(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of new fan mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "low"
    await common.async_set_fan_mode(hass, "high", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with("fan-mode-topic", "high", 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "high"


async def test_set_swing_mode_bad_attr(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test setting swing mode without required attribute."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "off"
    with pytest.raises(vol.Invalid) as excinfo:
        await common.async_set_swing_mode(hass, None, ENTITY_CLIMATE)
    assert "string value is None for dictionary value @ data['swing_mode']" in str(
        excinfo.value
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "off"


async def test_set_swing_pessimistic(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting swing mode in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["swing_mode_state_topic"] = "swing-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") is None

    await common.async_set_swing_mode(hass, "on", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") is None

    async_fire_mqtt_message(hass, "swing-state", "on")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "on"

    async_fire_mqtt_message(hass, "swing-state", "bogus state")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "on"


async def test_set_swing(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of new swing mode."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "off"
    await common.async_set_swing_mode(hass, "on", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with("swing-mode-topic", "on", 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "on"


async def test_set_target_temperature(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting the target temperature."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 21
    await common.async_set_hvac_mode(hass, "heat", ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "heat"
    mqtt_mock.async_publish.assert_called_once_with("mode-topic", "heat", 0, False)
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(hass, temperature=47, entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 47
    mqtt_mock.async_publish.assert_called_once_with(
        "temperature-topic", "47.0", 0, False
    )

    # also test directly supplying the operation mode to set_temperature
    mqtt_mock.async_publish.reset_mock()
    await common.async_set_temperature(
        hass, temperature=21, hvac_mode="cool", entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"
    assert state.attributes.get("temperature") == 21
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("mode-topic", "cool", 0, False),
            call("temperature-topic", "21.0", 0, False),
        ]
    )
    mqtt_mock.async_publish.reset_mock()


async def test_set_target_temperature_pessimistic(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test setting the target temperature."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["temperature_state_topic"] = "temperature-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") is None
    await common.async_set_hvac_mode(hass, "heat", ENTITY_CLIMATE)
    await common.async_set_temperature(hass, temperature=47, entity_id=ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") is None

    async_fire_mqtt_message(hass, "temperature-state", "1701")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 1701

    async_fire_mqtt_message(hass, "temperature-state", "not a number")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 1701


async def test_set_target_temperature_low_high(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting the low/high target temperature."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await common.async_set_temperature(
        hass, target_temp_low=20, target_temp_high=23, entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 20
    assert state.attributes.get("target_temp_high") == 23
    mqtt_mock.async_publish.assert_any_call("temperature-low-topic", "20.0", 0, False)
    mqtt_mock.async_publish.assert_any_call("temperature-high-topic", "23.0", 0, False)


async def test_set_target_temperature_low_highpessimistic(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test setting the low/high target temperature."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["temperature_low_state_topic"] = "temperature-low-state"
    config["climate"]["temperature_high_state_topic"] = "temperature-high-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") is None
    assert state.attributes.get("target_temp_high") is None
    await common.async_set_temperature(
        hass, target_temp_low=20, target_temp_high=23, entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") is None
    assert state.attributes.get("target_temp_high") is None

    async_fire_mqtt_message(hass, "temperature-low-state", "1701")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 1701
    assert state.attributes.get("target_temp_high") is None

    async_fire_mqtt_message(hass, "temperature-high-state", "1703")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 1701
    assert state.attributes.get("target_temp_high") == 1703

    async_fire_mqtt_message(hass, "temperature-low-state", "not a number")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 1701

    async_fire_mqtt_message(hass, "temperature-high-state", "not a number")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_high") == 1703


async def test_receive_mqtt_temperature(hass, mqtt_mock_entry_with_yaml_config):
    """Test getting the current temperature via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["current_temperature_topic"] = "current_temperature"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "current_temperature", "47")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("current_temperature") == 47


async def test_handle_action_received(hass, mqtt_mock_entry_with_yaml_config):
    """Test getting the action received via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["action_topic"] = "action"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # Cycle through valid modes and also check for wrong input such as "None" (str(None))
    async_fire_mqtt_message(hass, "action", "None")
    state = hass.states.get(ENTITY_CLIMATE)
    hvac_action = state.attributes.get(ATTR_HVAC_ACTION)
    assert hvac_action is None
    # Redefine actions according to https://developers.home-assistant.io/docs/core/entity/climate/#hvac-action
    actions = ["off", "heating", "cooling", "drying", "idle", "fan"]
    assert all(elem in actions for elem in CURRENT_HVAC_ACTIONS)
    for action in actions:
        async_fire_mqtt_message(hass, "action", action)
        state = hass.states.get(ENTITY_CLIMATE)
        hvac_action = state.attributes.get(ATTR_HVAC_ACTION)
        assert hvac_action == action


async def test_set_preset_mode_optimistic(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test setting of the preset mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "none"

    await common.async_set_preset_mode(hass, "away", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-topic", "away", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "away"

    await common.async_set_preset_mode(hass, "eco", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-topic", "eco", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "eco"

    await common.async_set_preset_mode(hass, "none", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-topic", "none", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "none"

    await common.async_set_preset_mode(hass, "comfort", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-topic", "comfort", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "comfort"

    await common.async_set_preset_mode(hass, "invalid", ENTITY_CLIMATE)
    assert "'invalid' is not a valid preset mode" in caplog.text


async def test_set_preset_mode_pessimistic(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test setting of the preset mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["preset_mode_state_topic"] = "preset-mode-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "none"

    async_fire_mqtt_message(hass, "preset-mode-state", "away")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "away"

    async_fire_mqtt_message(hass, "preset-mode-state", "eco")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "eco"

    async_fire_mqtt_message(hass, "preset-mode-state", "none")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "none"

    async_fire_mqtt_message(hass, "preset-mode-state", "comfort")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "comfort"

    async_fire_mqtt_message(hass, "preset-mode-state", "None")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "none"

    async_fire_mqtt_message(hass, "preset-mode-state", "home")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "home"

    async_fire_mqtt_message(hass, "preset-mode-state", "nonsense")
    assert (
        "'nonsense' received on topic preset-mode-state. 'nonsense' is not a valid preset mode"
        in caplog.text
    )

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "home"


async def test_set_aux_pessimistic(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of the aux heating in pessimistic mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["aux_state_topic"] = "aux-state"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"

    await common.async_set_aux_heat(hass, True, ENTITY_CLIMATE)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"

    async_fire_mqtt_message(hass, "aux-state", "ON")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "on"

    async_fire_mqtt_message(hass, "aux-state", "OFF")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"

    async_fire_mqtt_message(hass, "aux-state", "nonsense")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"


async def test_set_aux(hass, mqtt_mock_entry_with_yaml_config):
    """Test setting of the aux heating."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"
    await common.async_set_aux_heat(hass, True, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with("aux-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "on"

    await common.async_set_aux_heat(hass, False, ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with("aux-topic", "OFF", 0, False)
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"


async def test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_get_target_temperature_low_high_with_templates(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test getting temperature high/low with templates."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["temperature_low_state_topic"] = "temperature-state"
    config["climate"]["temperature_high_state_topic"] = "temperature-state"
    config["climate"]["temperature_low_state_template"] = "{{ value_json.temp_low }}"
    config["climate"]["temperature_high_state_template"] = "{{ value_json.temp_high }}"

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)

    # Temperature - with valid value
    assert state.attributes.get("target_temp_low") is None
    assert state.attributes.get("target_temp_high") is None

    async_fire_mqtt_message(
        hass, "temperature-state", '{"temp_low": "1031", "temp_high": "1032"}'
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 1031
    assert state.attributes.get("target_temp_high") == 1032

    # Temperature - with invalid value
    async_fire_mqtt_message(hass, "temperature-state", '"-INVALID-"')
    state = hass.states.get(ENTITY_CLIMATE)
    # make sure, the invalid value gets logged...
    assert "Could not parse temperature from" in caplog.text
    # ... but the actual value stays unchanged.
    assert state.attributes.get("target_temp_low") == 1031
    assert state.attributes.get("target_temp_high") == 1032


async def test_get_with_templates(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test getting various attributes with templates."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    # By default, just unquote the JSON-strings
    config["climate"]["value_template"] = "{{ value_json }}"
    config["climate"]["action_template"] = "{{ value_json }}"
    # Rendering to a bool for aux heat
    config["climate"]["aux_state_template"] = "{{ value == 'switchmeon' }}"
    # Rendering preset_mode
    config["climate"]["preset_mode_value_template"] = "{{ value_json.attribute }}"

    config["climate"]["action_topic"] = "action"
    config["climate"]["mode_state_topic"] = "mode-state"
    config["climate"]["fan_mode_state_topic"] = "fan-state"
    config["climate"]["swing_mode_state_topic"] = "swing-state"
    config["climate"]["temperature_state_topic"] = "temperature-state"
    config["climate"]["aux_state_topic"] = "aux-state"
    config["climate"]["current_temperature_topic"] = "current-temperature"
    config["climate"]["preset_mode_state_topic"] = "current-preset-mode"
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # Operation Mode
    state = hass.states.get(ENTITY_CLIMATE)
    async_fire_mqtt_message(hass, "mode-state", '"cool"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"

    # Fan Mode
    assert state.attributes.get("fan_mode") is None
    async_fire_mqtt_message(hass, "fan-state", '"high"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "high"

    # Swing Mode
    assert state.attributes.get("swing_mode") is None
    async_fire_mqtt_message(hass, "swing-state", '"on"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "on"

    # Temperature - with valid value
    assert state.attributes.get("temperature") is None
    async_fire_mqtt_message(hass, "temperature-state", '"1031"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 1031

    # Temperature - with invalid value
    async_fire_mqtt_message(hass, "temperature-state", '"-INVALID-"')
    state = hass.states.get(ENTITY_CLIMATE)
    # make sure, the invalid value gets logged...
    assert "Could not parse temperature from -INVALID-" in caplog.text
    # ... but the actual value stays unchanged.
    assert state.attributes.get("temperature") == 1031

    # Preset Mode
    assert state.attributes.get("preset_mode") == "none"
    async_fire_mqtt_message(hass, "current-preset-mode", '{"attribute": "eco"}')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == "eco"
    # Test with an empty json
    async_fire_mqtt_message(
        hass, "current-preset-mode", '{"other_attribute": "some_value"}'
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert "Ignoring empty preset_mode from 'current-preset-mode'"
    assert state.attributes.get("preset_mode") == "eco"

    # Aux mode
    assert state.attributes.get("aux_heat") == "off"
    async_fire_mqtt_message(hass, "aux-state", "switchmeon")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "on"

    # anything other than 'switchmeon' should turn Aux mode off
    async_fire_mqtt_message(hass, "aux-state", "somerandomstring")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("aux_heat") == "off"

    # Current temperature
    async_fire_mqtt_message(hass, "current-temperature", '"74656"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("current_temperature") == 74656

    # Action
    async_fire_mqtt_message(hass, "action", '"cooling"')
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("hvac_action") == "cooling"

    # Test ignoring null values
    async_fire_mqtt_message(hass, "action", "null")
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("hvac_action") == "cooling"
    assert (
        "Invalid ['cooling', 'drying', 'fan', 'heating', 'idle', 'off'] action: None, ignoring"
        in caplog.text
    )


async def test_set_and_templates(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test setting various attributes with templates."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    # Create simple templates
    config["climate"]["fan_mode_command_template"] = "fan_mode: {{ value }}"
    config["climate"]["preset_mode_command_template"] = "preset_mode: {{ value }}"
    config["climate"]["mode_command_template"] = "mode: {{ value }}"
    config["climate"]["swing_mode_command_template"] = "swing_mode: {{ value }}"
    config["climate"]["temperature_command_template"] = "temp: {{ value }}"
    config["climate"]["temperature_high_command_template"] = "temp_hi: {{ value }}"
    config["climate"]["temperature_low_command_template"] = "temp_lo: {{ value }}"

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    # Fan Mode
    await common.async_set_fan_mode(hass, "high", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "fan-mode-topic", "fan_mode: high", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("fan_mode") == "high"

    # Preset Mode
    await common.async_set_preset_mode(hass, PRESET_ECO, ENTITY_CLIMATE)
    mqtt_mock.async_publish.call_count == 1
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-topic", "preset_mode: eco", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("preset_mode") == PRESET_ECO

    # Mode
    await common.async_set_hvac_mode(hass, "cool", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-topic", "mode: cool", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.state == "cool"

    # Swing Mode
    await common.async_set_swing_mode(hass, "on", ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "swing-mode-topic", "swing_mode: on", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("swing_mode") == "on"

    # Temperature
    await common.async_set_temperature(hass, temperature=47, entity_id=ENTITY_CLIMATE)
    mqtt_mock.async_publish.assert_called_once_with(
        "temperature-topic", "temp: 47.0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 47

    # Temperature Low/High
    await common.async_set_temperature(
        hass, target_temp_low=20, target_temp_high=23, entity_id=ENTITY_CLIMATE
    )
    mqtt_mock.async_publish.assert_any_call(
        "temperature-low-topic", "temp_lo: 20.0", 0, False
    )
    mqtt_mock.async_publish.assert_any_call(
        "temperature-high-topic", "temp_hi: 23.0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("target_temp_low") == 20
    assert state.attributes.get("target_temp_high") == 23


async def test_min_temp_custom(hass, mqtt_mock_entry_with_yaml_config):
    """Test a custom min temp."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["min_temp"] = 26

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    min_temp = state.attributes.get("min_temp")

    assert isinstance(min_temp, float)
    assert state.attributes.get("min_temp") == 26


async def test_max_temp_custom(hass, mqtt_mock_entry_with_yaml_config):
    """Test a custom max temp."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["max_temp"] = 60

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    max_temp = state.attributes.get("max_temp")

    assert isinstance(max_temp, float)
    assert max_temp == 60


async def test_temp_step_custom(hass, mqtt_mock_entry_with_yaml_config):
    """Test a custom temp step."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["temp_step"] = 0.01

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(ENTITY_CLIMATE)
    temp_step = state.attributes.get("target_temp_step")

    assert isinstance(temp_step, float)
    assert temp_step == 0.01


async def test_temperature_unit(hass, mqtt_mock_entry_with_yaml_config):
    """Test that setting temperature unit converts temperature values."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["temperature_unit"] = "F"
    config["climate"]["current_temperature_topic"] = "current_temperature"

    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "current_temperature", "77")

    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("current_temperature") == 25


async def test_setting_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        CLIMATE_DOMAIN,
        DEFAULT_CONFIG,
        MQTT_CLIMATE_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry_with_yaml_config, caplog, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock_entry_with_yaml_config, caplog, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry_no_yaml_config, caplog, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test unique id option only creates one climate per unique_id."""
    config = {
        CLIMATE_DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "power_state_topic": "test-topic",
                "power_command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "power_state_topic": "test-topic",
                "power_command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, CLIMATE_DOMAIN, config
    )


@pytest.mark.parametrize(
    "topic,value,attribute,attribute_value",
    [
        ("action_topic", "heating", ATTR_HVAC_ACTION, "heating"),
        ("action_topic", "cooling", ATTR_HVAC_ACTION, "cooling"),
        ("aux_state_topic", "ON", ATTR_AUX_HEAT, "on"),
        ("current_temperature_topic", "22.1", ATTR_CURRENT_TEMPERATURE, 22.1),
        ("fan_mode_state_topic", "low", ATTR_FAN_MODE, "low"),
        ("mode_state_topic", "cool", None, None),
        ("mode_state_topic", "fan_only", None, None),
        ("swing_mode_state_topic", "on", ATTR_SWING_MODE, "on"),
        ("temperature_low_state_topic", "19.1", ATTR_TARGET_TEMP_LOW, 19.1),
        ("temperature_high_state_topic", "22.9", ATTR_TARGET_TEMP_HIGH, 22.9),
        ("temperature_state_topic", "19.9", ATTR_TEMPERATURE, 19.9),
    ],
)
async def test_encoding_subscribable_topics(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    topic,
    value,
    attribute,
    attribute_value,
):
    """Test handling of incoming encoded payload."""
    config = copy.deepcopy(DEFAULT_CONFIG[CLIMATE_DOMAIN])
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        CLIMATE_DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
    )


async def test_discovery_removal_climate(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test removal of discovered climate."""
    data = json.dumps(DEFAULT_CONFIG[CLIMATE_DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, CLIMATE_DOMAIN, data
    )


async def test_discovery_update_climate(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered climate."""
    config1 = {"name": "Beer"}
    config2 = {"name": "Milk"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, CLIMATE_DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_climate(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test update of discovered climate."""
    data1 = '{ "name": "Beer" }'
    with patch(
        "homeassistant.components.mqtt.climate.MqttClimate.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            CLIMATE_DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "power_command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk", "power_command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, CLIMATE_DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT climate device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT climate device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock_entry_with_yaml_config):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        CLIMATE_DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "mode_state_topic": "test-topic",
            "availability_topic": "avty-topic",
        }
    }
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock_entry_with_yaml_config,
        CLIMATE_DOMAIN,
        config,
        ["test-topic", "avty-topic"],
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, CLIMATE_DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT debug info."""
    config = {
        CLIMATE_DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "mode_command_topic": "command-topic",
            "mode_state_topic": "test-topic",
        }
    }
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        CLIMATE_DOMAIN,
        config,
        climate.SERVICE_TURN_ON,
        command_topic="command-topic",
        command_payload="heat",
        state_topic="test-topic",
    )


async def test_precision_default(hass, mqtt_mock_entry_with_yaml_config):
    """Test that setting precision to tenths works as intended."""
    assert await async_setup_component(hass, CLIMATE_DOMAIN, DEFAULT_CONFIG)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 23.7
    mqtt_mock.async_publish.reset_mock()


async def test_precision_halves(hass, mqtt_mock_entry_with_yaml_config):
    """Test that setting precision to halves works as intended."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["precision"] = 0.5
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 23.5
    mqtt_mock.async_publish.reset_mock()


async def test_precision_whole(hass, mqtt_mock_entry_with_yaml_config):
    """Test that setting precision to whole works as intended."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["climate"]["precision"] = 1.0
    assert await async_setup_component(hass, CLIMATE_DOMAIN, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await common.async_set_temperature(
        hass, temperature=23.67, entity_id=ENTITY_CLIMATE
    )
    state = hass.states.get(ENTITY_CLIMATE)
    assert state.attributes.get("temperature") == 24.0
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (
            climate.SERVICE_TURN_ON,
            "power_command_topic",
            None,
            "ON",
            None,
        ),
        (
            climate.SERVICE_SET_HVAC_MODE,
            "mode_command_topic",
            {"hvac_mode": "cool"},
            "cool",
            "mode_command_template",
        ),
        (
            climate.SERVICE_SET_PRESET_MODE,
            "preset_mode_command_topic",
            {"preset_mode": "sleep"},
            "sleep",
            "preset_mode_command_template",
        ),
        (
            climate.SERVICE_SET_FAN_MODE,
            "fan_mode_command_topic",
            {"fan_mode": "medium"},
            "medium",
            "fan_mode_command_template",
        ),
        (
            climate.SERVICE_SET_SWING_MODE,
            "swing_mode_command_topic",
            {"swing_mode": "on"},
            "on",
            "swing_mode_command_template",
        ),
        (
            climate.SERVICE_SET_AUX_HEAT,
            "aux_command_topic",
            {"aux_heat": "on"},
            "ON",
            None,
        ),
        (
            climate.SERVICE_SET_TEMPERATURE,
            "temperature_command_topic",
            {"temperature": "20.1"},
            20.1,
            "temperature_command_template",
        ),
        (
            climate.SERVICE_SET_TEMPERATURE,
            "temperature_low_command_topic",
            {
                "temperature": "20.1",
                "target_temp_low": "15.1",
                "target_temp_high": "29.8",
            },
            15.1,
            "temperature_low_command_template",
        ),
        (
            climate.SERVICE_SET_TEMPERATURE,
            "temperature_high_command_topic",
            {
                "temperature": "20.1",
                "target_temp_low": "15.1",
                "target_temp_high": "29.8",
            },
            29.8,
            "temperature_high_command_template",
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    service,
    topic,
    parameters,
    payload,
    template,
):
    """Test publishing MQTT payload with different encoding."""
    domain = climate.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[domain])
    if topic != "preset_mode_command_topic":
        del config["preset_mode_command_topic"]
        del config["preset_modes"]

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = CLIMATE_DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_reloadable_late(hass, mqtt_client_mock, caplog, tmp_path):
    """Test reloading the MQTT platform with late entry setup."""
    domain = CLIMATE_DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable_late(hass, caplog, tmp_path, domain, config)


async def test_setup_manual_entity_from_yaml(hass):
    """Test setup manual configured MQTT entity."""
    platform = CLIMATE_DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[platform])
    config["name"] = "test"
    del config["platform"]
    await help_test_setup_manual_entity_from_yaml(hass, platform, config)
    assert hass.states.get(f"{platform}.test") is not None


async def test_unload_entry(hass, mqtt_mock_entry_with_yaml_config, tmp_path):
    """Test unloading the config entry."""
    domain = climate.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
