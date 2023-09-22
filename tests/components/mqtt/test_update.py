"""The tests for mqtt update component."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, update
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant

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
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        update.DOMAIN: {
            "name": "test",
            "state_topic": "test-topic",
            "latest_version_topic": "test-topic",
            "command_topic": "test-topic",
            "payload_install": "install",
        }
    }
}


@pytest.fixture(autouse=True)
def update_platform_only():
    """Only setup the update platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.UPDATE]):
        yield


@pytest.mark.parametrize(
    ("hass_config", "device_class"),
    [
        (
            {
                mqtt.DOMAIN: {
                    update.DOMAIN: {
                        "state_topic": "test/installed-version",
                        "latest_version_topic": "test/latest-version",
                        "name": "Test Update",
                        "release_summary": "Test release summary",
                        "release_url": "https://example.com/release",
                        "title": "Test Update Title",
                        "entity_picture": "https://example.com/icon.png",
                        "device_class": "firmware",
                    }
                }
            },
            "firmware",
        ),
        (
            {
                mqtt.DOMAIN: {
                    update.DOMAIN: {
                        "state_topic": "test/installed-version",
                        "latest_version_topic": "test/latest-version",
                        "name": "Test Update",
                        "release_summary": "Test release summary",
                        "release_url": "https://example.com/release",
                        "title": "Test Update Title",
                        "entity_picture": "https://example.com/icon.png",
                        "device_class": None,
                    }
                }
            },
            None,
        ),
    ],
)
async def test_run_update_setup(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_class: str | None,
) -> None:
    """Test that it fetches the given payload."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, installed_version_topic, "1.9.0")
    async_fire_mqtt_message(hass, latest_version_topic, "1.9.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"
    assert state.attributes.get("release_summary") == "Test release summary"
    assert state.attributes.get("release_url") == "https://example.com/release"
    assert state.attributes.get("title") == "Test Update Title"
    assert state.attributes.get("entity_picture") == "https://example.com/icon.png"
    assert state.attributes.get("device_class") == device_class

    async_fire_mqtt_message(hass, latest_version_topic, "2.0.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/installed-version",
                    "latest_version_topic": "test/latest-version",
                    "name": "Test Update",
                    "release_summary": "Test release summary",
                    "release_url": "https://example.com/release",
                    "title": "Test Update Title",
                    "entity_picture": "https://example.com/icon.png",
                }
            }
        }
    ],
)
async def test_run_update_setup_float(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload when the version is parsable as a number."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, installed_version_topic, "1.9")
    async_fire_mqtt_message(hass, latest_version_topic, "1.9")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9"
    assert state.attributes.get("latest_version") == "1.9"
    assert state.attributes.get("release_summary") == "Test release summary"
    assert state.attributes.get("release_url") == "https://example.com/release"
    assert state.attributes.get("title") == "Test Update Title"
    assert state.attributes.get("entity_picture") == "https://example.com/icon.png"

    async_fire_mqtt_message(hass, latest_version_topic, "2.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9"
    assert state.attributes.get("latest_version") == "2.0"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/installed-version",
                    "value_template": "{{ value_json.installed }}",
                    "latest_version_topic": "test/latest-version",
                    "latest_version_template": "{{ value_json.latest }}",
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_value_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload with a template."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, installed_version_topic, '{"installed":"1.9.0"}')
    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"1.9.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"
    assert (
        state.attributes.get("entity_picture")
        == "https://brands.home-assistant.io/_/mqtt/icon.png"
    )

    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"2.0.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/installed-version",
                    "value_template": "{{ value_json.installed }}",
                    "latest_version_topic": "test/latest-version",
                    "latest_version_template": "{{ value_json.latest }}",
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_value_template_float(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload with a template when the version is parsable as a number."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, installed_version_topic, '{"installed":"1.9"}')
    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"1.9"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9"
    assert state.attributes.get("latest_version") == "1.9"
    assert (
        state.attributes.get("entity_picture")
        == "https://brands.home-assistant.io/_/mqtt/icon.png"
    )

    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"2.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9"
    assert state.attributes.get("latest_version") == "2.0"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/state-topic",
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_empty_json_state_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test an empty JSON payload."""
    state_topic = "test/state-topic"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, state_topic, "{}")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/state-topic",
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_json_state_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test whether it fetches data from a JSON payload."""
    state_topic = "test/state-topic"
    await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass,
        state_topic,
        '{"installed_version":"1.9.0","latest_version":"1.9.0",'
        '"title":"Test Update 1 Title","release_url":"https://example.com/release1",'
        '"release_summary":"Test release summary 1",'
        '"entity_picture": "https://example.com/icon1.png"}',
    )

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"
    assert state.attributes.get("release_summary") == "Test release summary 1"
    assert state.attributes.get("release_url") == "https://example.com/release1"
    assert state.attributes.get("title") == "Test Update 1 Title"
    assert state.attributes.get("entity_picture") == "https://example.com/icon1.png"

    async_fire_mqtt_message(
        hass,
        state_topic,
        '{"installed_version":"1.9.0","latest_version":"2.0.0",'
        '"title":"Test Update 2 Title","entity_picture":"https://example.com/icon2.png"}',
    )

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"
    assert state.attributes.get("entity_picture") == "https://example.com/icon2.png"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/state-topic",
                    "value_template": '{{ {"installed_version": value_json.installed, '
                    '"latest_version": value_json.latest} | to_json }}',
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_json_state_message_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test whether it fetches data from a JSON payload with template."""
    state_topic = "test/state-topic"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, state_topic, '{"installed":"1.9.0","latest":"1.9.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"

    async_fire_mqtt_message(hass, state_topic, '{"installed":"1.9.0","latest":"2.0.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "state_topic": "test/installed-version",
                    "latest_version_topic": "test/latest-version",
                    "command_topic": "test/install-command",
                    "payload_install": "install",
                    "name": "Test Update",
                }
            }
        }
    ],
)
async def test_run_install_service(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that install service works."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    command_topic = "test/install-command"

    mqtt_mock = await mqtt_mock_entry()

    async_fire_mqtt_message(hass, installed_version_topic, "1.9.0")
    async_fire_mqtt_message(hass, latest_version_topic, "2.0.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.test_update"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(command_topic, "install", 0, False)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, update.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
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
        update.DOMAIN,
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
        update.DOMAIN,
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
        update.DOMAIN,
        DEFAULT_CONFIG,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                update.DOMAIN: [
                    {
                        "name": "Bear",
                        "state_topic": "installed-topic",
                        "latest_version_topic": "latest-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Milk",
                        "state_topic": "installed-topic",
                        "latest_version_topic": "latest-topic",
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
    """Test unique id option only creates one update per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, update.DOMAIN)


async def test_discovery_removal_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered update."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][update.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry, caplog, update.DOMAIN, data
    )


async def test_discovery_update_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered update."""
    config1 = {
        "name": "Beer",
        "state_topic": "installed-topic",
        "latest_version_topic": "latest-topic",
    }
    config2 = {
        "name": "Milk",
        "state_topic": "installed-topic",
        "latest_version_topic": "latest-topic",
    }

    await help_test_discovery_update(
        hass, mqtt_mock_entry, caplog, update.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered update."""
    data1 = '{ "name": "Beer", "state_topic": "installed-topic", "latest_version_topic": "latest-topic"}'
    with patch(
        "homeassistant.components.mqtt.update.MqttUpdate.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            caplog,
            update.DOMAIN,
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
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "state_topic": "installed-topic", "latest_version_topic": "latest-topic" }'

    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, update.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT update device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT update device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, update.DOMAIN, DEFAULT_CONFIG
    )


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
    platform = update.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = update.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test reloading the MQTT platform."""
    domain = update.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)
