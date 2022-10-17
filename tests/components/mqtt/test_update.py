"""The tests for mqtt update component."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, update
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.setup import async_setup_component

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        update.DOMAIN: {
            "name": "test",
            "installed_version_topic": "installed-version-topic",
            "latest_version_topic": "installed-version-topic",
            "command_topic": "command-topic",
            "payload_install": "install",
        }
    }
}

# Test deprecated YAML configuration under the platform key
# Scheduled to be removed in HA core 2022.12
DEFAULT_CONFIG_LEGACY = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN])
DEFAULT_CONFIG_LEGACY[update.DOMAIN]["platform"] = mqtt.DOMAIN


@pytest.fixture(autouse=True)
def update_platform_only():
    """Only setup the update platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.UPDATE]):
        yield


async def test_run_update_setup(hass, mqtt_mock_entry_with_yaml_config):
    """Test that it fetches the given payload."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "installed_version_topic": installed_version_topic,
                    "latest_version_topic": latest_version_topic,
                    "name": "Test Update",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, installed_version_topic, "1.9.0")
    async_fire_mqtt_message(hass, latest_version_topic, "1.9.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"

    async_fire_mqtt_message(hass, latest_version_topic, "2.0.0")

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"


async def test_value_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test that it fetches the given payload with a template."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "installed_version_topic": installed_version_topic,
                    "installed_version_template": "{{ value_json.installed }}",
                    "latest_version_topic": latest_version_topic,
                    "latest_version_template": "{{ value_json.latest }}",
                    "name": "Test Update",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, installed_version_topic, '{"installed":"1.9.0"}')
    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"1.9.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_OFF
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "1.9.0"

    async_fire_mqtt_message(hass, latest_version_topic, '{"latest":"2.0.0"}')

    await hass.async_block_till_done()

    state = hass.states.get("update.test_update")
    assert state.state == STATE_ON
    assert state.attributes.get("installed_version") == "1.9.0"
    assert state.attributes.get("latest_version") == "2.0.0"


async def test_run_install_service(hass, mqtt_mock_entry_with_yaml_config):
    """Test that install service works."""
    installed_version_topic = "test/installed-version"
    latest_version_topic = "test/latest-version"
    command_topic = "test/install-command"

    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                update.DOMAIN: {
                    "installed_version_topic": installed_version_topic,
                    "latest_version_topic": latest_version_topic,
                    "command_topic": command_topic,
                    "payload_install": "install",
                    "name": "Test Update",
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

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
