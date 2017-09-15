"""Test for smart home alexa support."""
import asyncio

import pytest

from homeassistant.components.alexa import smart_home


def test_create_api_message():
    """Create a API message."""
    msg = smart_home.api_message('testName', 'testNameSpace')

    assert msg['header']['messageId'] is not None
    assert msg['header']['name'] == 'testName'
    assert msg['header']['namespace'] == 'testNameSpace'
    assert msg['header']['payloadVersion'] == '2'
    assert msg['payload'] == {}


@asyncio.coroutine
def test_wrong_version(hass):
    """Test with wrong version."""
    msg = smart_home.api_message('testName', 'testNameSpace')
    msg['header']['payloadVersion'] = '3'

    with pytest.raises(AssertionError):
        yield from smart_home.async_handle_message(hass, msg)
