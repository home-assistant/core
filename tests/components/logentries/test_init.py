"""The tests for the Logentries component."""

from unittest.mock import ANY, call, patch

import pytest

from homeassistant.components import logentries
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


async def test_setup_config_full(hass: HomeAssistant) -> None:
    """Test setup with all data."""
    config = {"logentries": {"token": "secret"}}
    assert await async_setup_component(hass, logentries.DOMAIN, config)

    with patch("homeassistant.components.logentries.requests.post") as mock_post:
        hass.states.async_set("fake.entity", STATE_ON)
        await hass.async_block_till_done()
        assert len(mock_post.mock_calls) == 1


async def test_setup_config_defaults(hass: HomeAssistant) -> None:
    """Test setup with defaults."""
    config = {"logentries": {"token": "token"}}
    assert await async_setup_component(hass, logentries.DOMAIN, config)

    with patch("homeassistant.components.logentries.requests.post") as mock_post:
        hass.states.async_set("fake.entity", STATE_ON)
        await hass.async_block_till_done()
        assert len(mock_post.mock_calls) == 1


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


async def test_event_listener(hass: HomeAssistant, mock_dump, mock_requests) -> None:
    """Test event listener."""
    mock_dump.side_effect = lambda x: x
    mock_post = mock_requests.post
    mock_requests.exceptions.RequestException = Exception
    config = {"logentries": {"token": "token"}}
    assert await async_setup_component(hass, logentries.DOMAIN, config)

    valid = {"1": 1, "1.0": 1.0, STATE_ON: 1, STATE_OFF: 0, "foo": "foo"}
    for in_, out in valid.items():
        payload = {
            "host": "https://webhook.logentries.com/noformat/logs/token",
            "event": [
                {
                    "domain": "fake",
                    "entity_id": "entity",
                    "attributes": {},
                    "time": ANY,
                    "value": out,
                }
            ],
        }
        hass.states.async_set("fake.entity", in_)
        await hass.async_block_till_done()
        assert mock_post.call_count == 1
        assert mock_post.call_args == call(payload["host"], data=payload, timeout=10)
        mock_post.reset_mock()
