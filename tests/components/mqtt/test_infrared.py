"""The tests for the MQTT infrared platform."""

import logging
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from infrared_protocols.commands.nec import NECCommand
import orjson
import pytest

from homeassistant.components import infrared, mqtt
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
import homeassistant.util.dt as dt_util

from .common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_discovery_removal,
    help_test_discovery_update_attr,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG_EMITTER = {
    mqtt.DOMAIN: {
        infrared.DOMAIN: {
            "schema": "emitter",
            "name": "test",
            "command_topic": "test-topic",
        }
    }
}
DEFAULT_CONFIG_RECEIVER = {
    mqtt.DOMAIN: {
        infrared.DOMAIN: {
            "schema": "receiver",
            "name": "test",
            "state_topic": "test-topic",
        }
    }
}

TEST_COMMAND = NECCommand(address=0x04FB, command=0x08F7, modulation=38000)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG_RECEIVER])
async def test_receiving_command_success(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test receiving an infrared command via subscription is successful."""
    payload_data = {
        "timings": TEST_COMMAND.get_raw_timings(),
        "modulation": TEST_COMMAND.modulation,
    }
    payload = orjson.dumps(payload_data).decode()

    now = dt_util.utcnow()
    freezer.move_to(now)

    await mqtt_mock_entry()

    received_signals: list[infrared.InfraredReceivedSignal] = []

    def _handle_received_signal(signal: infrared.InfraredReceivedSignal) -> None:
        """Handle the infrared signal."""
        received_signals.append(signal)

    unsubscribe = infrared.async_subscribe_receiver(
        hass, "infrared.test", _handle_received_signal
    )
    async_fire_mqtt_message(hass, "test-topic", payload, 0, False)
    await hass.async_block_till_done()

    assert len(received_signals) == 1
    signal = received_signals[0]
    assert signal.modulation == TEST_COMMAND.modulation
    assert signal.timings == TEST_COMMAND.get_raw_timings()

    state = hass.states.get("infrared.test")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")

    unsubscribe()


@pytest.mark.parametrize(
    ("payload", "log_message", "level"),
    [
        (
            "",
            "Ignoring payload for infrared.test on topic test-topic, with template None",
            logging.DEBUG,
        ),
        (
            "None",
            "Ignoring payload for infrared.test on topic test-topic, with template None",
            logging.DEBUG,
        ),
        (
            "invalid",
            "Invalid message received for infrared.test on topic test-topic, with template None",
            logging.WARNING,
        ),
        (
            '{"timings":null}',
            "Invalid message received for infrared.test on topic test-topic, with template None",
            logging.WARNING,
        ),
        (
            '{"timings":[]}',
            "Invalid message received for infrared.test on topic test-topic, with template None",
            logging.WARNING,
        ),
        (
            '{"timings":["1","2"],"modulation":38000}',
            "Invalid message received for infrared.test on topic test-topic, with template None",
            logging.WARNING,
        ),
    ],
)
@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG_RECEIVER])
async def test_receiving_command_unsuccessful(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    payload: str,
    log_message: str,
    level: int,
) -> None:
    """Test receiving an infrared command via subscription fails."""
    await mqtt_mock_entry()

    received_signals: list[infrared.InfraredReceivedSignal] = []

    def _handle_received_signal(signal: infrared.InfraredReceivedSignal) -> None:
        """Handle the infrared signal."""
        received_signals.append(signal)

    unsubscribe = infrared.async_subscribe_receiver(
        hass, "infrared.test", _handle_received_signal
    )

    with caplog.at_level(level):
        async_fire_mqtt_message(hass, "test-topic", payload, 0, False)
        await hass.async_block_till_done()
        assert log_message in caplog.text

    assert len(received_signals) == 0

    state = hass.states.get("infrared.test")
    assert state is not None
    assert state.state == STATE_UNKNOWN

    unsubscribe()


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG_EMITTER])
async def test_async_send_command_success(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test sending command via async_send_command helper."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    mqtt_mock = await mqtt_mock_entry()

    expected_payload_data = {
        "timings": TEST_COMMAND.get_raw_timings(),
        "modulation": TEST_COMMAND.modulation,
        "repeat_count": TEST_COMMAND.repeat_count,
    }
    expected_payload = orjson.dumps(expected_payload_data).decode()

    await infrared.async_send_command(hass, "infrared.test", TEST_COMMAND)

    mqtt_mock.async_publish.assert_called_with(
        "test-topic", expected_payload, 0, False, message_expiry_interval=None
    )

    state = hass.states.get("infrared.test")
    assert state is not None
    assert state.state == now.isoformat(timespec="milliseconds")


@pytest.mark.parametrize(
    "hass_config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER]
)
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, infrared.DOMAIN
    )


@pytest.mark.parametrize(
    "hass_config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER]
)
async def test_availability_without_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    hass_config: ConfigType,
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, infrared.DOMAIN, hass_config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, infrared.DOMAIN, config, None
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_setting_attribute_with_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    config: dict[str, Any],
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                infrared.DOMAIN: [
                    {
                        "name": "Test 1",
                        "schema": "emitter",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "schema": "emitter",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id_emitter(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one infrared emitter per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, infrared.DOMAIN)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                infrared.DOMAIN: [
                    {
                        "name": "Test 1",
                        "schema": "receiver",
                        "state_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "schema": "receiver",
                        "state_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id_receiver(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one infrared receiver per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, infrared.DOMAIN)


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_discovery_removal_infrared_entity(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test removal of discovered infrared entity."""
    data = orjson.dumps(config[mqtt.DOMAIN][infrared.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock_entry, infrared.DOMAIN, data)


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_entity_device_info_with_connection(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test MQTT infrared device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_entity_device_info_with_identifier(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test MQTT infrared device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_entity_device_info_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_entity_device_info_remove(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_RECEIVER])
async def test_entity_id_update_subscriptions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_entity_id_update_discovery_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, infrared.DOMAIN, config
    )


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient, config: dict[str, Any]
) -> None:
    """Test reloading the MQTT platform."""
    domain = infrared.DOMAIN
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    "hass_config",
    [
        DEFAULT_CONFIG_EMITTER,
        {"mqtt": [DEFAULT_CONFIG_EMITTER["mqtt"]]},
        DEFAULT_CONFIG_RECEIVER,
        {"mqtt": [DEFAULT_CONFIG_RECEIVER["mqtt"]]},
    ],
    ids=[
        "platform_key_emitter",
        "listed_emitter",
        "platform_key_receiver",
        "listed_receiver",
    ],
)
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = infrared.DOMAIN
    assert hass.states.get(f"{platform}.test")


@pytest.mark.parametrize("config", [DEFAULT_CONFIG_EMITTER, DEFAULT_CONFIG_RECEIVER])
async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    config: dict[str, Any],
) -> None:
    """Test unloading the config entry."""
    domain = infrared.DOMAIN
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )
