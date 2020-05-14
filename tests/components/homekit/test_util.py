"""Test HomeKit util module."""
import pytest
import voluptuous as vol

from homeassistant.components.homekit.const import (
    CONF_FEATURE,
    CONF_FEATURE_LIST,
    CONF_LINKED_BATTERY_SENSOR,
    CONF_LOW_BATTERY_THRESHOLD,
    DEFAULT_CONFIG_FLOW_PORT,
    DOMAIN,
    FEATURE_ON_OFF,
    FEATURE_PLAY_PAUSE,
    HOMEKIT_PAIRING_QR,
    HOMEKIT_PAIRING_QR_SECRET,
    TYPE_FAUCET,
    TYPE_OUTLET,
    TYPE_SHOWER,
    TYPE_SPRINKLER,
    TYPE_SWITCH,
    TYPE_VALVE,
)
from homeassistant.components.homekit.util import (
    HomeKitSpeedMapping,
    SpeedRange,
    cleanup_name_for_homekit,
    convert_to_float,
    density_to_air_quality,
    dismiss_setup_message,
    find_next_available_port,
    port_is_available,
    show_setup_message,
    temperature_to_homekit,
    temperature_to_states,
    validate_entity_config as vec,
    validate_media_player_features,
)
from homeassistant.components.persistent_notification import (
    ATTR_MESSAGE,
    ATTR_NOTIFICATION_ID,
    DOMAIN as PERSISTENT_NOTIFICATION_DOMAIN,
)
from homeassistant.const import (
    ATTR_CODE,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    CONF_TYPE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import State

from .util import async_init_integration

from tests.common import async_mock_service


def test_validate_entity_config():
    """Test validate entities."""
    configs = [
        None,
        [],
        "string",
        12345,
        {"invalid_entity_id": {}},
        {"demo.test": 1},
        {"binary_sensor.demo": {CONF_LINKED_BATTERY_SENSOR: None}},
        {"binary_sensor.demo": {CONF_LINKED_BATTERY_SENSOR: "switch.demo"}},
        {"binary_sensor.demo": {CONF_LOW_BATTERY_THRESHOLD: "switch.demo"}},
        {"binary_sensor.demo": {CONF_LOW_BATTERY_THRESHOLD: -10}},
        {"demo.test": "test"},
        {"demo.test": [1, 2]},
        {"demo.test": None},
        {"demo.test": {CONF_NAME: None}},
        {"media_player.test": {CONF_FEATURE_LIST: [{CONF_FEATURE: "invalid_feature"}]}},
        {
            "media_player.test": {
                CONF_FEATURE_LIST: [
                    {CONF_FEATURE: FEATURE_ON_OFF},
                    {CONF_FEATURE: FEATURE_ON_OFF},
                ]
            }
        },
        {"switch.test": {CONF_TYPE: "invalid_type"}},
    ]

    for conf in configs:
        with pytest.raises(vol.Invalid):
            vec(conf)

    assert vec({}) == {}
    assert vec({"demo.test": {CONF_NAME: "Name"}}) == {
        "demo.test": {CONF_NAME: "Name", CONF_LOW_BATTERY_THRESHOLD: 20}
    }

    assert vec(
        {"binary_sensor.demo": {CONF_LINKED_BATTERY_SENSOR: "sensor.demo_battery"}}
    ) == {
        "binary_sensor.demo": {
            CONF_LINKED_BATTERY_SENSOR: "sensor.demo_battery",
            CONF_LOW_BATTERY_THRESHOLD: 20,
        }
    }
    assert vec({"binary_sensor.demo": {CONF_LOW_BATTERY_THRESHOLD: 50}}) == {
        "binary_sensor.demo": {CONF_LOW_BATTERY_THRESHOLD: 50}
    }

    assert vec({"alarm_control_panel.demo": {}}) == {
        "alarm_control_panel.demo": {ATTR_CODE: None, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"alarm_control_panel.demo": {ATTR_CODE: "1234"}}) == {
        "alarm_control_panel.demo": {ATTR_CODE: "1234", CONF_LOW_BATTERY_THRESHOLD: 20}
    }

    assert vec({"lock.demo": {}}) == {
        "lock.demo": {ATTR_CODE: None, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"lock.demo": {ATTR_CODE: "1234"}}) == {
        "lock.demo": {ATTR_CODE: "1234", CONF_LOW_BATTERY_THRESHOLD: 20}
    }

    assert vec({"media_player.demo": {}}) == {
        "media_player.demo": {CONF_FEATURE_LIST: {}, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    config = {
        CONF_FEATURE_LIST: [
            {CONF_FEATURE: FEATURE_ON_OFF},
            {CONF_FEATURE: FEATURE_PLAY_PAUSE},
        ]
    }
    assert vec({"media_player.demo": config}) == {
        "media_player.demo": {
            CONF_FEATURE_LIST: {FEATURE_ON_OFF: {}, FEATURE_PLAY_PAUSE: {}},
            CONF_LOW_BATTERY_THRESHOLD: 20,
        }
    }

    assert vec({"switch.demo": {CONF_TYPE: TYPE_FAUCET}}) == {
        "switch.demo": {CONF_TYPE: TYPE_FAUCET, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"switch.demo": {CONF_TYPE: TYPE_OUTLET}}) == {
        "switch.demo": {CONF_TYPE: TYPE_OUTLET, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"switch.demo": {CONF_TYPE: TYPE_SHOWER}}) == {
        "switch.demo": {CONF_TYPE: TYPE_SHOWER, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"switch.demo": {CONF_TYPE: TYPE_SPRINKLER}}) == {
        "switch.demo": {CONF_TYPE: TYPE_SPRINKLER, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"switch.demo": {CONF_TYPE: TYPE_SWITCH}}) == {
        "switch.demo": {CONF_TYPE: TYPE_SWITCH, CONF_LOW_BATTERY_THRESHOLD: 20}
    }
    assert vec({"switch.demo": {CONF_TYPE: TYPE_VALVE}}) == {
        "switch.demo": {CONF_TYPE: TYPE_VALVE, CONF_LOW_BATTERY_THRESHOLD: 20}
    }


def test_validate_media_player_features():
    """Test validate modes for media players."""
    config = {}
    attrs = {ATTR_SUPPORTED_FEATURES: 20873}
    entity_state = State("media_player.demo", "on", attrs)
    assert validate_media_player_features(entity_state, config) is True

    config = {FEATURE_ON_OFF: None}
    assert validate_media_player_features(entity_state, config) is True

    entity_state = State("media_player.demo", "on")
    assert validate_media_player_features(entity_state, config) is False


def test_convert_to_float():
    """Test convert_to_float method."""
    assert convert_to_float(12) == 12
    assert convert_to_float(12.4) == 12.4
    assert convert_to_float(STATE_UNKNOWN) is None
    assert convert_to_float(None) is None


def test_cleanup_name_for_homekit():
    """Ensure name sanitize works as expected."""

    assert cleanup_name_for_homekit("abc") == "abc"
    assert cleanup_name_for_homekit("a b c") == "a b c"
    assert cleanup_name_for_homekit("ab_c") == "ab c"
    assert (
        cleanup_name_for_homekit('ab!@#$%^&*()-=":.,><?//\\ frog')
        == "ab--#---&----- -.,------ frog"
    )
    assert cleanup_name_for_homekit("の日本_語文字セット") == "の日本 語文字セット"


def test_temperature_to_homekit():
    """Test temperature conversion from HA to HomeKit."""
    assert temperature_to_homekit(20.46, TEMP_CELSIUS) == 20.5
    assert temperature_to_homekit(92.1, TEMP_FAHRENHEIT) == 33.4


def test_temperature_to_states():
    """Test temperature conversion from HomeKit to HA."""
    assert temperature_to_states(20, TEMP_CELSIUS) == 20.0
    assert temperature_to_states(20.2, TEMP_FAHRENHEIT) == 68.5


def test_density_to_air_quality():
    """Test map PM2.5 density to HomeKit AirQuality level."""
    assert density_to_air_quality(0) == 1
    assert density_to_air_quality(35) == 1
    assert density_to_air_quality(35.1) == 2
    assert density_to_air_quality(75) == 2
    assert density_to_air_quality(115) == 3
    assert density_to_air_quality(150) == 4
    assert density_to_air_quality(300) == 5


async def test_show_setup_msg(hass):
    """Test show setup message as persistence notification."""
    pincode = b"123-45-678"

    entry = await async_init_integration(hass)
    assert entry

    call_create_notification = async_mock_service(
        hass, PERSISTENT_NOTIFICATION_DOMAIN, "create"
    )

    await hass.async_add_executor_job(
        show_setup_message, hass, entry.entry_id, "bridge_name", pincode, "X-HM://0"
    )
    await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id][HOMEKIT_PAIRING_QR_SECRET]
    assert hass.data[DOMAIN][entry.entry_id][HOMEKIT_PAIRING_QR]

    assert call_create_notification
    assert call_create_notification[0].data[ATTR_NOTIFICATION_ID] == entry.entry_id
    assert pincode.decode() in call_create_notification[0].data[ATTR_MESSAGE]


async def test_dismiss_setup_msg(hass):
    """Test dismiss setup message."""
    call_dismiss_notification = async_mock_service(
        hass, PERSISTENT_NOTIFICATION_DOMAIN, "dismiss"
    )

    await hass.async_add_executor_job(dismiss_setup_message, hass, "entry_id")
    await hass.async_block_till_done()

    assert call_dismiss_notification
    assert call_dismiss_notification[0].data[ATTR_NOTIFICATION_ID] == "entry_id"


def test_homekit_speed_mapping():
    """Test if the SpeedRanges from a speed_list are as expected."""
    # A standard 2-speed fan
    speed_mapping = HomeKitSpeedMapping(["off", "low", "high"])
    assert speed_mapping.speed_ranges == {
        "off": SpeedRange(0, 0),
        "low": SpeedRange(100 / 3, 50),
        "high": SpeedRange(200 / 3, 100),
    }

    # A standard 3-speed fan
    speed_mapping = HomeKitSpeedMapping(["off", "low", "medium", "high"])
    assert speed_mapping.speed_ranges == {
        "off": SpeedRange(0, 0),
        "low": SpeedRange(100 / 4, 100 / 3),
        "medium": SpeedRange(200 / 4, 200 / 3),
        "high": SpeedRange(300 / 4, 100),
    }

    # a Dyson-like fan with 10 speeds
    speed_mapping = HomeKitSpeedMapping([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    assert speed_mapping.speed_ranges == {
        0: SpeedRange(0, 0),
        1: SpeedRange(10, 100 / 9),
        2: SpeedRange(20, 200 / 9),
        3: SpeedRange(30, 300 / 9),
        4: SpeedRange(40, 400 / 9),
        5: SpeedRange(50, 500 / 9),
        6: SpeedRange(60, 600 / 9),
        7: SpeedRange(70, 700 / 9),
        8: SpeedRange(80, 800 / 9),
        9: SpeedRange(90, 100),
    }


def test_speed_to_homekit():
    """Test speed conversion from HA to Homekit."""
    speed_mapping = HomeKitSpeedMapping(["off", "low", "high"])
    assert speed_mapping.speed_to_homekit(None) is None
    assert speed_mapping.speed_to_homekit("off") == 0
    assert speed_mapping.speed_to_homekit("low") == 50
    assert speed_mapping.speed_to_homekit("high") == 100


def test_speed_to_states():
    """Test speed conversion from Homekit to HA."""
    speed_mapping = HomeKitSpeedMapping(["off", "low", "high"])
    assert speed_mapping.speed_to_states(-1) == "off"
    assert speed_mapping.speed_to_states(0) == "off"
    assert speed_mapping.speed_to_states(33) == "off"
    assert speed_mapping.speed_to_states(34) == "low"
    assert speed_mapping.speed_to_states(50) == "low"
    assert speed_mapping.speed_to_states(66) == "low"
    assert speed_mapping.speed_to_states(67) == "high"
    assert speed_mapping.speed_to_states(100) == "high"


async def test_port_is_available(hass):
    """Test we can get an available port and it is actually available."""
    next_port = await hass.async_add_executor_job(
        find_next_available_port, DEFAULT_CONFIG_FLOW_PORT
    )
    assert next_port

    assert await hass.async_add_executor_job(port_is_available, next_port)
