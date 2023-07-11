"""Configure tests for the Trello integration."""
from collections.abc import Awaitable, Callable, Coroutine
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.trello.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture

ComponentSetup = Callable[[], Awaitable[None]]

CONF_USER_ID = "user_id"
CONF_USER_EMAIL = "user_email"
CONF_BOARD_IDS = "board_ids"


def mock_fetch_json(path="trello/batch.json"):
    """Mock response from Trello client."""
    return json.loads(load_fixture(path))


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Mock a config entry then set up the component."""
    mock_config_entry = MockConfigEntry(
        domain="trello",
        title="foo@example.com",
        data={
            CONF_API_KEY: "abc123",
            CONF_API_TOKEN: "123abc",
            CONF_USER_ID: "12345",
            CONF_USER_EMAIL: "foo@example.com",
        },
        options={
            CONF_BOARD_IDS: [
                "3a634d47a4cb1e9a9886a2e3",
                "bea542e091bc1bfe5e780c8f",
                "0c6646739c3a12b1bf3dfd3a",
            ]
        },
    )
    mock_config_entry.add_to_hass(hass)

    async def func() -> None:
        with patch(
            "homeassistant.components.trello.sensor.TrelloClient.fetch_json",
            return_value=mock_fetch_json("trello/batch.json"),
        ):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()

    return func
