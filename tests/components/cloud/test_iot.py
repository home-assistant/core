"""Test the cloud.iot module."""
import asyncio
from unittest.mock import patch, MagicMock

import pytest

from homeassistant.components.alexa import smart_home
from homeassistant.components.cloud import iot, Cloud, MODE_DEV
from tests.common import mock_coro


@pytest.fixture
def mock_client():
    """Mock the IoT client."""
    with patch('homeassistant.components.cloud.iot._client_factory') as client:
        client = client()
        client.connect.return_value = True
        yield client


@asyncio.coroutine
def test_cloud_calling_handler(mock_client):
    """Test we call handle message with correct info."""
    hass = MagicMock()
    cloud = Cloud(hass, MODE_DEV)
    client = iot.CloudIoT(cloud)

    client.connect()

    assert len(mock_client.mock_calls) == 2
    callback = mock_client.mock_calls[1][1][2]

    callback(None, None, MagicMock(
        topic='thing_id/i/alexa/123456',
        payload='hello payload'
    ))

    assert len(hass.mock_calls) == 2
    _, _, _, handler, message_id, payload = hass.mock_calls[1][1]
    assert handler == 'alexa'
    assert message_id == '123456'
    assert payload == 'hello payload'


@asyncio.coroutine
def test_handler_forwarding():
    """Test we forward messages to correct handler."""
    handler = MagicMock()
    handler.return_value = mock_coro()
    hass = object()
    cloud = object()
    with patch.dict(iot.HANDLERS, {'test': handler}):
        yield from iot.async_handle_message(
            hass, cloud, 'test', '123456', 'payload')

    assert len(handler.mock_calls) == 1
    r_hass, r_cloud, message_id, payload = handler.mock_calls[0][1]
    assert r_hass is hass
    assert r_cloud is cloud
    assert message_id == '123456'
    assert payload == 'payload'


@asyncio.coroutine
def test_handler_alexa():
    """Test we handle Alexa messages correctly."""
    hass = MagicMock()
    hass.async_add_job.return_value = mock_coro()
    cloud = MagicMock()

    with patch(
        'homeassistant.components.alexa.smart_home.async_handle_message',
            return_value=mock_coro({
                smart_home.ATTR_PAYLOAD: {'hello': 456}
            })) as mock_alexa:
        yield from iot.async_handle_alexa(
            hass, cloud, '123456', '{"test": 123}')

    assert len(mock_alexa.mock_calls) == 1
    r_hass, message = mock_alexa.mock_calls[0][1]
    assert hass is r_hass
    assert message == {'test': 123}

    assert len(hass.async_add_job.mock_calls) == 1
    publish, topic, payload = hass.async_add_job.mock_calls[0][1]
    assert publish is cloud.iot.publish
    assert topic == 'alexa/123456'
    assert payload == '{"hello": 456}'
