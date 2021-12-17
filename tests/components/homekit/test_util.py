"""Test HomeKit util module."""
from unittest.mock import MagicMock, Mock, patch

import pytest
import voluptuous as vol

from homeassistant.components.homekit.const import (
    BRIDGE_NAME,
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
    accessory_friendly_name,
    async_dismiss_setup_message,
    async_find_next_available_port,
    async_port_is_available,
    async_show_setup_message,
    cleanup_name_for_homekit,
    convert_to_float,
    density_to_air_quality,
    format_sw_version,
    state_needs_accessory_mode,
    temperature_to_homekit,
    temperature_to_states,
    validate_entity_config as vec,
    validate_media_player_features,
)
from homeassistant.components.persistent_notification import async_create, async_dismiss
from homeassistant.const import (
    ATTR_CODE,
    ATTR_SUPPORTED_FEATURES,
    CONF_NAME,
    CONF_PORT,
    CONF_TYPE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import State

from .util import async_init_integration

from tests.common import MockConfigEntry


def _mock_socket(failure_attempts: int = 0) -> MagicMock:
    """Mock a socket that fails to bind failure_attempts amount of times."""
    mock_socket = MagicMock()
    attempts = 0

    def _simulate_bind(*_):
        nonlocal attempts
        attempts += 1
        if attempts <= failure_attempts:
            raise OSError
        return

    mock_socket.bind = Mock(side_effect=_simulate_bind)
    return mock_socket


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


async def test_async_show_setup_msg(hass, hk_driver, mock_get_source_ip):
    """Test show setup message as persistence notification."""
    pincode = b"123-45-678"

    entry = await async_init_integration(hass)
    assert entry

    with patch(
        "homeassistant.components.persistent_notification.async_create",
        side_effect=async_create,
    ) as mock_create:
        async_show_setup_message(
            hass, entry.entry_id, "bridge_name", pincode, "X-HM://0"
        )
        await hass.async_block_till_done()
    assert hass.data[DOMAIN][entry.entry_id][HOMEKIT_PAIRING_QR_SECRET]
    assert hass.data[DOMAIN][entry.entry_id][HOMEKIT_PAIRING_QR]

    assert len(mock_create.mock_calls) == 1
    assert mock_create.mock_calls[0][1][3] == entry.entry_id
    assert pincode.decode() in mock_create.mock_calls[0][1][1]


async def test_async_dismiss_setup_msg(hass):
    """Test dismiss setup message."""
    with patch(
        "homeassistant.components.persistent_notification.async_dismiss",
        side_effect=async_dismiss,
    ) as mock_dismiss:
        async_dismiss_setup_message(hass, "entry_id")
        await hass.async_block_till_done()

    assert len(mock_dismiss.mock_calls) == 1
    assert mock_dismiss.mock_calls[0][1][1] == "entry_id"


async def test_port_is_available(hass):
    """Test we can get an available port and it is actually available."""
    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(0),
    ):
        next_port = async_find_next_available_port(hass, DEFAULT_CONFIG_FLOW_PORT)
    assert next_port
    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(0),
    ):
        assert async_port_is_available(next_port)

    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(5),
    ):
        next_port = async_find_next_available_port(hass, DEFAULT_CONFIG_FLOW_PORT)
    assert next_port == DEFAULT_CONFIG_FLOW_PORT + 5
    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(0),
    ):
        assert async_port_is_available(next_port)

    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(1),
    ):
        assert not async_port_is_available(next_port)


async def test_port_is_available_skips_existing_entries(hass):
    """Test we can get an available port and it is actually available."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_NAME: BRIDGE_NAME, CONF_PORT: DEFAULT_CONFIG_FLOW_PORT},
        options={},
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(),
    ):
        next_port = async_find_next_available_port(hass, DEFAULT_CONFIG_FLOW_PORT)

    assert next_port == DEFAULT_CONFIG_FLOW_PORT + 1

    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(),
    ):
        assert async_port_is_available(next_port)

    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(4),
    ):
        next_port = async_find_next_available_port(hass, DEFAULT_CONFIG_FLOW_PORT)

    assert next_port == DEFAULT_CONFIG_FLOW_PORT + 5
    with patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(),
    ):
        assert async_port_is_available(next_port)

    with pytest.raises(OSError), patch(
        "homeassistant.components.homekit.util.socket.socket",
        return_value=_mock_socket(10),
    ):
        async_find_next_available_port(hass, 65530)


async def test_format_sw_version():
    """Test format_sw_version method."""
    assert format_sw_version("soho+3.6.8+soho-release-rt120+10") == "3.6.8"
    assert format_sw_version("undefined-undefined-1.6.8") == "1.6.8"
    assert format_sw_version("56.0-76060") == "56.0.76060"
    assert format_sw_version(3.6) == "3.6"
    assert format_sw_version("unknown") is None


async def test_accessory_friendly_name():
    """Test we provide a helpful friendly name."""

    accessory = Mock()
    accessory.display_name = "same"
    assert accessory_friendly_name("Same", accessory) == "Same"
    assert accessory_friendly_name("hass title", accessory) == "hass title (same)"
    accessory.display_name = "Hass title 123"
    assert accessory_friendly_name("hass title", accessory) == "Hass title 123"


async def test_lock_state_needs_accessory_mode(hass):
    """Test that locks are setup as accessories."""
    hass.states.async_set("lock.mine", "locked")
    assert state_needs_accessory_mode(hass.states.get("lock.mine")) is True
