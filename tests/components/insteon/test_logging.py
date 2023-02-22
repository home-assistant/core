"""Test the logging APIs."""

import logging

from homeassistant.components.insteon.api import async_load_api
from homeassistant.components.insteon.api.device import ID, TYPE
from homeassistant.components.insteon.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_INPUT_PLM

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def _async_setup(hass, hass_ws_client):
    """Set up for tests."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="abcde12345",
        data=MOCK_USER_INPUT_PLM,
        options={},
    )
    config_entry.add_to_hass(hass)
    async_load_api(hass)

    ws_client = await hass_ws_client(hass)
    return ws_client


async def _async_get_logging_test(ws_client, log_messages, log_topics, ws_id):
    """Run the get logging test."""
    await ws_client.send_json({ID: ws_id, TYPE: "insteon/logging/get"})
    msg = await ws_client.receive_json()
    result = msg["result"]
    assert result["messages"] == log_messages
    assert result["topics"] == log_topics


async def test_get_logging(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test getting the logging level of a device."""
    messages = logging.getLogger("pyinsteon.messages")
    topics = logging.getLogger("pyinsteon.topics")
    ws_client = await _async_setup(hass, hass_ws_client)

    messages.setLevel(logging.DEBUG)
    topics.setLevel(logging.WARNING)
    await _async_get_logging_test(ws_client, True, False, 1)

    messages.setLevel(logging.WARNING)
    topics.setLevel(logging.DEBUG)
    await _async_get_logging_test(ws_client, False, True, 2)

    messages.setLevel(logging.WARNING)
    topics.setLevel(logging.WARNING)
    await _async_get_logging_test(ws_client, False, False, 3)

    messages.setLevel(logging.DEBUG)
    topics.setLevel(logging.DEBUG)
    await _async_get_logging_test(ws_client, True, True, 4)


async def test_set_logging(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test setting the logging level of a device."""
    logging.getLogger("pyinsteon.messages")
    logging.getLogger("pyinsteon.topics")
    ws_client = await _async_setup(hass, hass_ws_client)

    await ws_client.send_json(
        {ID: 1, TYPE: "insteon/logging/set", "loggers": ["messages"]}
    )
    await _async_get_logging_test(ws_client, True, False, 2)

    await ws_client.send_json(
        {ID: 3, TYPE: "insteon/logging/set", "loggers": ["topics"]}
    )
    await _async_get_logging_test(ws_client, False, True, 4)

    await ws_client.send_json({ID: 5, TYPE: "insteon/logging/set", "loggers": []})
    await _async_get_logging_test(ws_client, False, False, 6)

    await ws_client.send_json(
        {ID: 7, TYPE: "insteon/logging/set", "loggers": ["messages", "topics"]}
    )
    await _async_get_logging_test(ws_client, True, True, 8)
