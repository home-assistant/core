"""The tests for the Tasmota light platform."""
import copy
import json
from unittest.mock import patch

from hatasmota.const import CONF_MAC
from hatasmota.utils import (
    get_topic_stat_result,
    get_topic_tele_state,
    get_topic_tele_will,
)

from homeassistant.components import light
from homeassistant.components.light import (
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    SUPPORT_EFFECT,
    SUPPORT_TRANSITION,
    SUPPORT_WHITE_VALUE,
)
from homeassistant.components.tasmota.const import DEFAULT_PREFIX
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON

from .test_common import (
    DEFAULT_CONFIG,
    help_test_availability,
    help_test_availability_discovery_update,
    help_test_availability_poll_state,
    help_test_availability_when_connection_lost,
    help_test_discovery_device_remove,
    help_test_discovery_removal,
    help_test_discovery_update_unchanged,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
)

from tests.common import async_fire_mqtt_message
from tests.components.light import common


async def test_attributes_on_off(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("min_mireds") is None
    assert state.attributes.get("max_mireds") is None
    assert state.attributes.get("supported_features") == 0


async def test_attributes_dimmer_tuya(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (dimmer)
    config["ty"] = 1  # Tuya device
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("min_mireds") is None
    assert state.attributes.get("max_mireds") is None
    assert state.attributes.get("supported_features") == SUPPORT_BRIGHTNESS


async def test_attributes_dimmer(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (dimmer)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("min_mireds") is None
    assert state.attributes.get("max_mireds") is None
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
    )


async def test_attributes_ct(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 2  # 2 channel light (CW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("min_mireds") == 153
    assert state.attributes.get("max_mireds") == 500
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_TRANSITION
    )


async def test_attributes_ct_reduced(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 2  # 2 channel light (CW)
    config["so"]["82"] = 1  # Reduced CT range
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") is None
    assert state.attributes.get("min_mireds") == 200
    assert state.attributes.get("max_mireds") == 380
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_TRANSITION
    )


async def test_attributes_rgb(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 3  # 3 channel light (RGB)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") == [
        "None",
        "Wake up",
        "Cycle up",
        "Cycle down",
        "Random",
    ]
    assert state.attributes.get("min_mireds") is None
    assert state.attributes.get("max_mireds") is None
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_EFFECT | SUPPORT_TRANSITION
    )


async def test_attributes_rgbw(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 4  # 5 channel light (RGBW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") == [
        "None",
        "Wake up",
        "Cycle up",
        "Cycle down",
        "Random",
    ]
    assert state.attributes.get("min_mireds") is None
    assert state.attributes.get("max_mireds") is None
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS
        | SUPPORT_COLOR
        | SUPPORT_EFFECT
        | SUPPORT_TRANSITION
        | SUPPORT_WHITE_VALUE
    )


async def test_attributes_rgbww(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") == [
        "None",
        "Wake up",
        "Cycle up",
        "Cycle down",
        "Random",
    ]
    assert state.attributes.get("min_mireds") == 153
    assert state.attributes.get("max_mireds") == 500
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS
        | SUPPORT_COLOR
        | SUPPORT_COLOR_TEMP
        | SUPPORT_EFFECT
        | SUPPORT_TRANSITION
        | SUPPORT_WHITE_VALUE
    )


async def test_attributes_rgbww_reduced(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    config["so"]["82"] = 1  # Reduced CT range
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.attributes.get("effect_list") == [
        "None",
        "Wake up",
        "Cycle up",
        "Cycle down",
        "Random",
    ]
    assert state.attributes.get("min_mireds") == 200
    assert state.attributes.get("max_mireds") == 380
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS
        | SUPPORT_COLOR
        | SUPPORT_COLOR_TEMP
        | SUPPORT_EFFECT
        | SUPPORT_TRANSITION
        | SUPPORT_WHITE_VALUE
    )


async def test_controlling_state_via_mqtt_on_off(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_mqtt_ct(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 2  # 2 channel light (CT)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","CT":300}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 300

    # Tasmota will send "Color" also for CT light, this should be ignored
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Color":"255,128"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 300
    assert state.attributes.get("brightness") == 127.5


async def test_controlling_state_via_mqtt_rgbww(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Color":"255,128,0"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 128, 0)

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 127.5
    # Setting white > 0 should clear the color
    assert not state.attributes.get("rgb_color")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","CT":300}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 300

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":0}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    # Setting white to 0 should clear the white_value and color_temp
    assert not state.attributes.get("white_value")
    assert not state.attributes.get("color_temp")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Scheme":3}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "Cycle down"

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_mqtt_rgbww_hex(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    config["so"]["17"] = 0  # Hex color in state updates
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Color":"FF8000"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 128, 0)

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Color":"00FF800000"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (0, 255, 128)

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 127.5
    # Setting white > 0 should clear the color
    assert not state.attributes.get("rgb_color")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","CT":300}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 300

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":0}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    # Setting white to 0 should clear the white_value and color_temp
    assert not state.attributes.get("white_value")
    assert not state.attributes.get("color_temp")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Scheme":3}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "Cycle down"

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_mqtt_rgbww_tuya(hass, mqtt_mock, setup_tasmota):
    """Test state update via MQTT."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    config["ty"] = 1  # Tuya device
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == "unavailable"
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Color":"255,128,0"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 128, 0)

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 127.5
    # Setting white > 0 should clear the color
    assert not state.attributes.get("rgb_color")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","CT":300}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 300

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","White":0}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    # Setting white to 0 should clear the white_value and color_temp
    assert not state.attributes.get("white_value")
    assert not state.attributes.get("color_temp")

    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Scheme":3}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "Cycle down"

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "tasmota_49A3BC/stat/RESULT", '{"POWER":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands_on_off(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT message is sent
    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Power1", "ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn the light off and verify MQTT message is sent
    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Power1", "OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_sending_mqtt_commands_rgbww_tuya(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    config["ty"] = 1  # Tuya device
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT message is sent
    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn the light off and verify MQTT message is sent
    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT messages are sent
    await common.async_turn_on(hass, "light.test", brightness=192)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Dimmer3 75", 0, False
    )


async def test_sending_mqtt_commands_rgbww(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT message is sent
    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn the light off and verify MQTT message is sent
    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT messages are sent
    await common.async_turn_on(hass, "light.test", brightness=192)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Dimmer 75", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Power1 ON;NoDelay;Color2 255,128,0",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", color_temp=200)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Power1 ON;NoDelay;CT 200",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", white_value=128)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Power1 ON;NoDelay;White 50",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", effect="Random")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Power1 ON;NoDelay;Scheme 4",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


async def test_sending_mqtt_commands_power_unlinked(hass, mqtt_mock, setup_tasmota):
    """Test the sending MQTT commands to a light with unlinked dimlevel and power."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (dimmer)
    config["so"]["20"] = 1  # Update of Dimmer/Color/CT without turning power on
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT message is sent
    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Tasmota is not optimistic, the state should still be off
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn the light off and verify MQTT message is sent
    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog", "NoDelay;Power1 OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn the light on and verify MQTT messages are sent; POWER should be sent
    await common.async_turn_on(hass, "light.test", brightness=192)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Dimmer 75;NoDelay;Power1 ON",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


async def test_transition(hass, mqtt_mock, setup_tasmota):
    """Test transition commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->100: Speed should be 4*2=8
    await common.async_turn_on(hass, "light.test", brightness=255, transition=4)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 8;NoDelay;Dimmer 100",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->100: Speed should be capped at 40
    await common.async_turn_on(hass, "light.test", brightness=255, transition=100)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 40;NoDelay;Dimmer 100",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->0: Speed should be 1
    await common.async_turn_on(hass, "light.test", brightness=0, transition=100)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 1;NoDelay;Power1 OFF",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->50: Speed should be 4*2*2=16
    await common.async_turn_on(hass, "light.test", brightness=128, transition=4)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 16;NoDelay;Dimmer 50",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5

    # Dim the light from 50->0: Speed should be 6*2*2=24
    await common.async_turn_off(hass, "light.test", transition=6)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 24;NoDelay;Power1 OFF",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":100}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    # Dim the light from 100->0: Speed should be 0
    await common.async_turn_off(hass, "light.test", transition=0)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 0;NoDelay;Power1 OFF",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/STATE",
        '{"POWER":"ON","Dimmer":50, "Color":"0,255,0"}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5
    assert state.attributes.get("rgb_color") == (0, 255, 0)

    # Set color of the light from 0,255,0 to 255,0,0 @ 50%: Speed should be 6*2*2=24
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 0, 0], transition=6)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 24;NoDelay;Power1 ON;NoDelay;Color2 255,0,0",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass,
        "tasmota_49A3BC/tele/STATE",
        '{"POWER":"ON","Dimmer":100, "Color":"0,255,0"}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("rgb_color") == (0, 255, 0)

    # Set color of the light from 0,255,0 to 255,0,0 @ 100%: Speed should be 6*2=12
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 0, 0], transition=6)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 12;NoDelay;Power1 ON;NoDelay;Color2 255,0,0",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50, "CT":153}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5
    assert state.attributes.get("color_temp") == 153

    # Set color_temp of the light from 153 to 500 @ 50%: Speed should be 6*2*2=24
    await common.async_turn_on(hass, "light.test", color_temp=500, transition=6)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 24;NoDelay;Power1 ON;NoDelay;CT 500",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Fake state update from the light
    async_fire_mqtt_message(
        hass, "tasmota_49A3BC/tele/STATE", '{"POWER":"ON","Dimmer":50, "CT":500}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 127.5
    assert state.attributes.get("color_temp") == 500

    # Set color_temp of the light from 500 to 326 @ 50%: Speed should be 6*2*2*2=48->40
    await common.async_turn_on(hass, "light.test", color_temp=326, transition=6)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 40;NoDelay;Power1 ON;NoDelay;CT 326",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


async def test_transition_fixed(hass, mqtt_mock, setup_tasmota):
    """Test transition commands."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 5  # 5 channel light (RGBCW)
    config["so"]["117"] = 1  # fading at fixed duration instead of fixed slew rate
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->100: Speed should be 4*2=8
    await common.async_turn_on(hass, "light.test", brightness=255, transition=4)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 8;NoDelay;Dimmer 100",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->100: Speed should be capped at 40
    await common.async_turn_on(hass, "light.test", brightness=255, transition=100)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 40;NoDelay;Dimmer 100",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->0: Speed should be 4*2=8
    await common.async_turn_on(hass, "light.test", brightness=0, transition=4)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 8;NoDelay;Power1 OFF",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->50: Speed should be 4*2=8
    await common.async_turn_on(hass, "light.test", brightness=128, transition=4)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 1;NoDelay;Speed 8;NoDelay;Dimmer 50",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Dim the light from 0->50: Speed should be 0
    await common.async_turn_on(hass, "light.test", brightness=128, transition=0)
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_49A3BC/cmnd/Backlog",
        "NoDelay;Fade 0;NoDelay;Dimmer 50",
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


async def test_relay_as_light(hass, mqtt_mock, setup_tasmota):
    """Test relay show up as light in light mode."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state is None
    state = hass.states.get("light.test")
    assert state is not None


async def _test_split_light(hass, mqtt_mock, config, num_lights, num_switches):
    """Test multi-channel light split to single-channel dimmers."""
    mac = config["mac"]

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("switch")) == num_switches
    assert len(hass.states.async_entity_ids("light")) == num_lights

    lights = hass.states.async_entity_ids("light")
    for idx, entity in enumerate(lights):
        mqtt_mock.async_publish.reset_mock()
        # Turn the light on and verify MQTT message is sent
        await common.async_turn_on(hass, entity)
        mqtt_mock.async_publish.assert_called_once_with(
            "tasmota_49A3BC/cmnd/Backlog",
            f"NoDelay;Power{idx+num_switches+1} ON",
            0,
            False,
        )

        mqtt_mock.async_publish.reset_mock()
        # Dim the light and verify MQTT message is sent
        await common.async_turn_on(hass, entity, brightness=(idx + 1) * 25.5)
        mqtt_mock.async_publish.assert_called_once_with(
            "tasmota_49A3BC/cmnd/Backlog",
            f"NoDelay;Channel{idx+num_switches+1} {(idx+1)*10}",
            0,
            False,
        )


async def test_split_light(hass, mqtt_mock, setup_tasmota):
    """Test multi-channel light split to single-channel dimmers."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["rl"][1] = 2
    config["rl"][2] = 2
    config["rl"][3] = 2
    config["rl"][4] = 2
    config["so"][68] = 1  # Multi-channel PWM instead of a single light
    config["lt_st"] = 5  # 5 channel light (RGBCW)

    await _test_split_light(hass, mqtt_mock, config, 5, 0)


async def test_split_light2(hass, mqtt_mock, setup_tasmota):
    """Test multi-channel light split to single-channel dimmers."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["rl"][1] = 1
    config["rl"][2] = 2
    config["rl"][3] = 2
    config["rl"][4] = 2
    config["rl"][5] = 2
    config["rl"][6] = 2
    config["so"][68] = 1  # Multi-channel PWM instead of a single light
    config["lt_st"] = 5  # 5 channel light (RGBCW)

    await _test_split_light(hass, mqtt_mock, config, 5, 2)


async def _test_unlinked_light(hass, mqtt_mock, config, num_switches):
    """Test rgbww light split to rgb+ww."""
    mac = config["mac"]
    num_lights = 2

    async_fire_mqtt_message(
        hass,
        f"{DEFAULT_PREFIX}/{mac}/config",
        json.dumps(config),
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "tasmota_49A3BC/tele/LWT", "Online")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    assert len(hass.states.async_entity_ids("switch")) == num_switches
    assert len(hass.states.async_entity_ids("light")) == num_lights

    lights = hass.states.async_entity_ids("light")
    for idx, entity in enumerate(lights):
        mqtt_mock.async_publish.reset_mock()
        # Turn the light on and verify MQTT message is sent
        await common.async_turn_on(hass, entity)
        mqtt_mock.async_publish.assert_called_once_with(
            "tasmota_49A3BC/cmnd/Backlog",
            f"NoDelay;Power{idx+num_switches+1} ON",
            0,
            False,
        )

        mqtt_mock.async_publish.reset_mock()
        # Dim the light and verify MQTT message is sent
        await common.async_turn_on(hass, entity, brightness=(idx + 1) * 25.5)
        mqtt_mock.async_publish.assert_called_once_with(
            "tasmota_49A3BC/cmnd/Backlog",
            f"NoDelay;Dimmer{idx+1} {(idx+1)*10}",
            0,
            False,
        )


async def test_unlinked_light(hass, mqtt_mock, setup_tasmota):
    """Test rgbww light split to rgb+ww."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["rl"][1] = 2
    config["lk"] = 0  # RGB + white channels unlinked
    config["lt_st"] = 5  # 5 channel light (RGBCW)

    await _test_unlinked_light(hass, mqtt_mock, config, 0)


async def test_unlinked_light2(hass, mqtt_mock, setup_tasmota):
    """Test rgbww light split to rgb+ww."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["rl"][1] = 1
    config["rl"][2] = 2
    config["rl"][3] = 2
    config["lk"] = 0  # RGB + white channels unlinked
    config["lt_st"] = 5  # 5 channel light (RGBCW)

    await _test_unlinked_light(hass, mqtt_mock, config, 2)


async def test_discovery_update_reconfigure_light(
    hass, mqtt_mock, caplog, setup_tasmota
):
    """Test reconfigure of discovered light."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 2
    config2["lt_st"] = 3  # 3 channel light (RGB)
    data1 = json.dumps(config)
    data2 = json.dumps(config2)

    # Simple dimmer
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data1)
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION
    )

    # Reconfigure as RGB light
    async_fire_mqtt_message(hass, f"{DEFAULT_PREFIX}/{config[CONF_MAC]}/config", data2)
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert (
        state.attributes.get("supported_features")
        == SUPPORT_BRIGHTNESS | SUPPORT_COLOR | SUPPORT_EFFECT | SUPPORT_TRANSITION
    )


async def test_availability_when_connection_lost(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test availability after MQTT disconnection."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    await help_test_availability_when_connection_lost(
        hass, mqtt_client_mock, mqtt_mock, light.DOMAIN, config
    )


async def test_availability(hass, mqtt_mock, setup_tasmota):
    """Test availability."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    await help_test_availability(hass, mqtt_mock, light.DOMAIN, config)


async def test_availability_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test availability discovery update."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    await help_test_availability_discovery_update(hass, mqtt_mock, light.DOMAIN, config)


async def test_availability_poll_state(
    hass, mqtt_client_mock, mqtt_mock, setup_tasmota
):
    """Test polling after MQTT connection (re)established."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    poll_topic = "tasmota_49A3BC/cmnd/STATE"
    await help_test_availability_poll_state(
        hass, mqtt_client_mock, mqtt_mock, light.DOMAIN, config, poll_topic, ""
    )


async def test_discovery_removal_light(hass, mqtt_mock, caplog, setup_tasmota):
    """Test removal of discovered light."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["rl"][0] = 2
    config1["lt_st"] = 1  # 1 channel light (Dimmer)
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 0
    config2["lt_st"] = 0

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, light.DOMAIN, config1, config2
    )


async def test_discovery_removal_relay_as_light(hass, mqtt_mock, caplog, setup_tasmota):
    """Test removal of discovered relay as light."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["rl"][0] = 1
    config1["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 1
    config2["so"]["30"] = 0  # Disable Home Assistant auto-discovery as light

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, light.DOMAIN, config1, config2
    )


async def test_discovery_removal_relay_as_light2(
    hass, mqtt_mock, caplog, setup_tasmota
):
    """Test removal of discovered relay as light."""
    config1 = copy.deepcopy(DEFAULT_CONFIG)
    config1["rl"][0] = 1
    config1["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    config2 = copy.deepcopy(DEFAULT_CONFIG)
    config2["rl"][0] = 0
    config2["so"]["30"] = 0  # Disable Home Assistant auto-discovery as light

    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, light.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_light(hass, mqtt_mock, caplog, setup_tasmota):
    """Test update of discovered light."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    with patch(
        "homeassistant.components.tasmota.light.TasmotaLight.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, light.DOMAIN, config, discovery_update
        )


async def test_discovery_device_remove(hass, mqtt_mock, setup_tasmota):
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    unique_id = f"{DEFAULT_CONFIG['mac']}_light_light_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, light.DOMAIN, unique_id, config
    )


async def test_discovery_device_remove_relay_as_light(hass, mqtt_mock, setup_tasmota):
    """Test device registry remove."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 1
    config["so"]["30"] = 1  # Enforce Home Assistant auto-discovery as light
    unique_id = f"{DEFAULT_CONFIG['mac']}_light_relay_0"
    await help_test_discovery_device_remove(
        hass, mqtt_mock, light.DOMAIN, unique_id, config
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock, setup_tasmota):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    topics = [
        get_topic_stat_result(config),
        get_topic_tele_state(config),
        get_topic_tele_will(config),
    ]
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, light.DOMAIN, config, topics
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock, setup_tasmota):
    """Test MQTT discovery update when entity_id is updated."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["rl"][0] = 2
    config["lt_st"] = 1  # 1 channel light (Dimmer)
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, light.DOMAIN, config
    )
