"""The tests for the Logentries component."""

from unittest.mock import MagicMock, call, patch

import pytest

import homeassistant.components.logentries as logentries
from homeassistant.const import EVENT_STATE_CHANGED, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component


async def test_setup_config_full(hass):
    """Test setup with all data."""
    config = {"logentries": {"token": "secret"}}
    hass.bus.listen = MagicMock()
    assert await async_setup_component(hass, logentries.DOMAIN, config)
    assert hass.bus.listen.called
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]


async def test_setup_config_defaults(hass):
    """Test setup with defaults."""
    config = {"logentries": {"token": "token"}}
    hass.bus.listen = MagicMock()
    assert await async_setup_component(hass, logentries.DOMAIN, config)
    assert hass.bus.listen.called
    assert EVENT_STATE_CHANGED == hass.bus.listen.call_args_list[0][0][0]


@pytest.fixture
def mock_dump():
    """Mock json dumps."""
    with patch("json.dumps") as mock_dump:
        yield mock_dump


@pytest.fixture
def mock_requests():
    """Mock requests."""
    with patch.object(logentries, "requests") as mock_requests:
        yield mock_requests


async def test_event_listener(hass, mock_dump, mock_requests):
    """Test event listener."""
    mock_dump.side_effect = lambda x: x
    mock_post = mock_requests.post
    mock_requests.exceptions.RequestException = Exception
    config = {"logentries": {"token": "token"}}
    hass.bus.listen = MagicMock()
    assert await async_setup_component(hass, logentries.DOMAIN, config)
    handler_method = hass.bus.listen.call_args_list[0][0][1]

    valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0, "foo": "foo"}
    for in_, out in valid.items():
        state = MagicMock(state=in_, domain="fake", object_id="entity", attributes={})
        event = MagicMock(data={"new_state": state}, time_fired=12345)
        body = [
            {
                "domain": "fake",
                "entity_id": "entity",
                "attributes": {},
                "time": "12345",
                "value": out,
            }
        ]
        payload = {
            "host": "https://webhook.logentries.com/noformat/logs/token",
            "event": body,
        }
        handler_method(event)
        assert mock_post.call_count == 1
        assert mock_post.call_args == call(payload["host"], data=payload, timeout=10)
        mock_post.reset_mock()
