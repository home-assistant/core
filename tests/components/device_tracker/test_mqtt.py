"""The tests for the MQTT device tracker platform."""
import logging
import os
from asynctest import patch
import pytest

from homeassistant.setup import async_setup_component
from homeassistant.components import device_tracker
from homeassistant.const import CONF_PLATFORM

from tests.common import (
    async_mock_mqtt_component, async_fire_mqtt_message)

_LOGGER = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def setup_comp(hass):
    """Initialize components."""
    hass.loop.run_until_complete(async_mock_mqtt_component(hass))
    yaml_devices = hass.config.path(device_tracker.YAML_DEVICES)
    yield
    if os.path.isfile(yaml_devices):
        os.remove(yaml_devices)


async def test_ensure_device_tracker_platform_validation(hass):
    """Test if platform validation was done."""
    async def mock_setup_scanner(hass, config, see, discovery_info=None):
        """Check that Qos was added by validation."""
        assert 'qos' in config

    with patch('homeassistant.components.device_tracker.mqtt.'
               'async_setup_scanner', autospec=True,
               side_effect=mock_setup_scanner) as mock_sp:

        dev_id = 'paulus'
        topic = '/location/paulus'
        assert await async_setup_component(hass, device_tracker.DOMAIN, {
            device_tracker.DOMAIN: {
                CONF_PLATFORM: 'mqtt',
                'devices': {dev_id: topic}
            }
        })
        assert mock_sp.call_count == 1


async def test_new_message(hass):
    """Test new message."""
    dev_id = 'paulus'
    entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
    topic = '/location/paulus'
    location = 'work'

    hass.config.components = set(['mqtt', 'zone'])
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'mqtt',
            'devices': {dev_id: topic}
        }
    })
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert location == hass.states.get(entity_id).state


async def test_single_level_wildcard_topic(hass):
    """Test single level wildcard topic."""
    dev_id = 'paulus'
    entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
    subscription = '/location/+/paulus'
    topic = '/location/room/paulus'
    location = 'work'

    hass.config.components = set(['mqtt', 'zone'])
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'mqtt',
            'devices': {dev_id: subscription}
        }
    })
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert location == hass.states.get(entity_id).state


async def test_multi_level_wildcard_topic(hass):
    """Test multi level wildcard topic."""
    dev_id = 'paulus'
    entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
    subscription = '/location/#'
    topic = '/location/room/paulus'
    location = 'work'

    hass.config.components = set(['mqtt', 'zone'])
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'mqtt',
            'devices': {dev_id: subscription}
        }
    })
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert location == hass.states.get(entity_id).state


async def test_single_level_wildcard_topic_not_matching(hass):
    """Test not matching single level wildcard topic."""
    dev_id = 'paulus'
    entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
    subscription = '/location/+/paulus'
    topic = '/location/paulus'
    location = 'work'

    hass.config.components = set(['mqtt', 'zone'])
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'mqtt',
            'devices': {dev_id: subscription}
        }
    })
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None


async def test_multi_level_wildcard_topic_not_matching(hass):
    """Test not matching multi level wildcard topic."""
    dev_id = 'paulus'
    entity_id = device_tracker.ENTITY_ID_FORMAT.format(dev_id)
    subscription = '/location/#'
    topic = '/somewhere/room/paulus'
    location = 'work'

    hass.config.components = set(['mqtt', 'zone'])
    assert await async_setup_component(hass, device_tracker.DOMAIN, {
        device_tracker.DOMAIN: {
            CONF_PLATFORM: 'mqtt',
            'devices': {dev_id: subscription}
        }
    })
    async_fire_mqtt_message(hass, topic, location)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id) is None
