"""The tests for the MQTT device tracker platform using configuration.yaml."""
from unittest.mock import patch

import pytest

from homeassistant.components.device_tracker.const import DOMAIN, SOURCE_TYPE_BLUETOOTH
from homeassistant.const import CONF_PLATFORM, STATE_HOME, STATE_NOT_HOME, Platform
from homeassistant.setup import async_setup_component

from .test_common import help_test_setup_manual_entity_from_yaml

from tests.common import async_fire_mqtt_message


@pytest.fixture(autouse=True)
def device_tracker_platform_only():
    """Only setup the device_tracker platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.DEVICE_TRACKER]):
        yield


# Deprecated in HA Core 2022.6
async def test_legacy_ensure_device_tracker_platform_validation(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test if platform validation was done."""

    async def mock_setup_scanner(hass, config, see, discovery_info=None):
        """Check that Qos was added by validation."""
        assert "qos" in config

    with patch(
        "homeassistant.components.mqtt.device_tracker.async_setup_scanner",
        autospec=True,
        side_effect=mock_setup_scanner,
    ) as mock_sp:

        dev_id = "paulus"
        topic = "/location/paulus"
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: topic}}}
        )
        await hass.async_block_till_done()
        await mqtt_mock_entry_with_yaml_config()
        assert mock_sp.call_count == 1


# Deprecated in HA Core 2022.6
async def test_legacy_new_message(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test new message."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    topic = "/location/paulus"
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: topic}}}
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == location


# Deprecated in HA Core 2022.6
async def test_legacy_single_level_wildcard_topic(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test single level wildcard topic."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    subscription = "/location/+/paulus"
    topic = "/location/room/paulus"
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == location


# Deprecated in HA Core 2022.6
async def test_legacy_multi_level_wildcard_topic(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test multi level wildcard topic."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    subscription = "/location/#"
    topic = "/location/room/paulus"
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == location


# Deprecated in HA Core 2022.6
async def test_legacy_single_level_wildcard_topic_not_matching(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test not matching single level wildcard topic."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    subscription = "/location/+/paulus"
    topic = "/location/paulus"
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None


# Deprecated in HA Core 2022.6
async def test_legacy_multi_level_wildcard_topic_not_matching(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test not matching multi level wildcard topic."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    subscription = "/location/#"
    topic = "/somewhere/room/paulus"
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {DOMAIN: {CONF_PLATFORM: "mqtt", "devices": {dev_id: subscription}}},
    )
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None


# Deprecated in HA Core 2022.6
async def test_legacy_matching_custom_payload_for_home_and_not_home(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test custom payload_home sets state to home and custom payload_not_home sets state to not_home."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    topic = "/location/paulus"
    payload_home = "present"
    payload_not_home = "not present"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_PLATFORM: "mqtt",
                "devices": {dev_id: topic},
                "payload_home": payload_home,
                "payload_not_home": payload_not_home,
            }
        },
    )
    async_fire_mqtt_message(hass, topic, payload_home)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_HOME

    async_fire_mqtt_message(hass, topic, payload_not_home)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_NOT_HOME


# Deprecated in HA Core 2022.6
async def test_legacy_not_matching_custom_payload_for_home_and_not_home(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test not matching payload does not set state to home or not_home."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    topic = "/location/paulus"
    payload_home = "present"
    payload_not_home = "not present"
    payload_not_matching = "test"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_PLATFORM: "mqtt",
                "devices": {dev_id: topic},
                "payload_home": payload_home,
                "payload_not_home": payload_not_home,
            }
        },
    )
    async_fire_mqtt_message(hass, topic, payload_not_matching)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_HOME
    assert hass.states.get(entity_id).state != STATE_NOT_HOME


# Deprecated in HA Core 2022.6
async def test_legacy_matching_source_type(
    hass, mock_device_tracker_conf, mqtt_mock_entry_no_yaml_config
):
    """Test setting source type."""
    await mqtt_mock_entry_no_yaml_config()
    dev_id = "paulus"
    entity_id = f"{DOMAIN}.{dev_id}"
    topic = "/location/paulus"
    source_type = SOURCE_TYPE_BLUETOOTH
    location = "work"

    hass.config.components = {"mqtt", "zone"}
    assert await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_PLATFORM: "mqtt",
                "devices": {dev_id: topic},
                "source_type": source_type,
            }
        },
    )

    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).attributes["source_type"] == SOURCE_TYPE_BLUETOOTH


async def test_setup_with_modern_schema(hass, mock_device_tracker_conf):
    """Test setup using the modern schema."""
    dev_id = "jan"
    entity_id = f"{DOMAIN}.{dev_id}"
    topic = "/location/jan"

    hass.config.components = {"zone"}
    config = {"name": dev_id, "state_topic": topic}

    await help_test_setup_manual_entity_from_yaml(hass, DOMAIN, config)

    assert hass.states.get(entity_id) is not None
