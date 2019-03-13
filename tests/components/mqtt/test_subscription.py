"""The tests for the MQTT subscription component."""
from unittest import mock

from homeassistant.components.mqtt.subscription import (
    async_subscribe_topics, async_unsubscribe_topics)
from homeassistant.core import callback

from tests.common import async_fire_mqtt_message, async_mock_mqtt_component


async def test_subscribe_topics(hass, mqtt_mock, caplog):
    """Test subscription to topics."""
    calls1 = []

    @callback
    def record_calls1(*args):
        """Record calls."""
        calls1.append(args)

    calls2 = []

    @callback
    def record_calls2(*args):
        """Record calls."""
        calls2.append(args)

    sub_state = None
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': record_calls1},
         'test_topic2': {'topic': 'test-topic2',
                         'msg_callback': record_calls2}})

    async_fire_mqtt_message(hass, 'test-topic1', 'test-payload1')
    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 'test-topic1' == calls1[0][0].topic
    assert 'test-payload1' == calls1[0][0].payload
    assert 0 == len(calls2)

    async_fire_mqtt_message(hass, 'test-topic2', 'test-payload2')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 1 == len(calls2)
    assert 'test-topic2' == calls2[0][0].topic
    assert 'test-payload2' == calls2[0][0].payload

    await async_unsubscribe_topics(hass, sub_state)

    async_fire_mqtt_message(hass, 'test-topic1', 'test-payload')
    async_fire_mqtt_message(hass, 'test-topic2', 'test-payload')

    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 1 == len(calls2)


async def test_modify_topics(hass, mqtt_mock, caplog):
    """Test modification of topics."""
    calls1 = []

    @callback
    def record_calls1(*args):
        """Record calls."""
        calls1.append(args)

    calls2 = []

    @callback
    def record_calls2(*args):
        """Record calls."""
        calls2.append(args)

    sub_state = None
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': record_calls1},
         'test_topic2': {'topic': 'test-topic2',
                         'msg_callback': record_calls2}})

    async_fire_mqtt_message(hass, 'test-topic1', 'test-payload')
    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 0 == len(calls2)

    async_fire_mqtt_message(hass, 'test-topic2', 'test-payload')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 1 == len(calls2)

    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1_1',
                         'msg_callback': record_calls1}})

    async_fire_mqtt_message(hass, 'test-topic1', 'test-payload')
    async_fire_mqtt_message(hass, 'test-topic2', 'test-payload')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert 1 == len(calls1)
    assert 1 == len(calls2)

    async_fire_mqtt_message(hass, 'test-topic1_1', 'test-payload')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert 2 == len(calls1)
    assert 'test-topic1_1' == calls1[1][0].topic
    assert 'test-payload' == calls1[1][0].payload
    assert 1 == len(calls2)

    await async_unsubscribe_topics(hass, sub_state)

    async_fire_mqtt_message(hass, 'test-topic1_1', 'test-payload')
    async_fire_mqtt_message(hass, 'test-topic2', 'test-payload')

    await hass.async_block_till_done()
    assert 2 == len(calls1)
    assert 1 == len(calls2)


async def test_qos_encoding_default(hass, mqtt_mock, caplog):
    """Test default qos and encoding."""
    mock_mqtt = await async_mock_mqtt_component(hass)

    @callback
    def msg_callback(*args):
        """Do nothing."""
        pass

    sub_state = None
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': msg_callback}})
    mock_mqtt.async_subscribe.assert_called_once_with(
        'test-topic1', mock.ANY, 0, 'utf-8')


async def test_qos_encoding_custom(hass, mqtt_mock, caplog):
    """Test custom qos and encoding."""
    mock_mqtt = await async_mock_mqtt_component(hass)

    @callback
    def msg_callback(*args):
        """Do nothing."""
        pass

    sub_state = None
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': msg_callback,
                         'qos': 1,
                         'encoding': 'utf-16'}})
    mock_mqtt.async_subscribe.assert_called_once_with(
        'test-topic1', mock.ANY, 1, 'utf-16')


async def test_no_change(hass, mqtt_mock, caplog):
    """Test subscription to topics without change."""
    mock_mqtt = await async_mock_mqtt_component(hass)

    @callback
    def msg_callback(*args):
        """Do nothing."""
        pass

    sub_state = None
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': msg_callback}})
    call_count = mock_mqtt.async_subscribe.call_count
    sub_state = await async_subscribe_topics(
        hass, sub_state,
        {'test_topic1': {'topic': 'test-topic1',
                         'msg_callback': msg_callback}})
    assert call_count == mock_mqtt.async_subscribe.call_count
