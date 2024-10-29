"""Configure tests for the Twinkly integration."""

from collections.abc import Awaitable, Callable, Coroutine
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TEST_MODEL, TEST_NAME, TEST_UID, ClientMock

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[ClientMock]]

DOMAIN = "twinkly"
TITLE = "Twinkly"


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Create Twinkly entry in Home Assistant."""
    client = ClientMock()
    return MockConfigEntry(
        domain=DOMAIN,
        title=TITLE,
        unique_id=TEST_UID,
        entry_id=TEST_UID,
        data={
            "host": client.host,
            "id": client.id,
            "name": TEST_NAME,
            "model": TEST_MODEL,
            "device_name": TEST_NAME,
        },
    )


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> Callable[[], Coroutine[Any, Any, ClientMock]]:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    async def func() -> ClientMock:
        mock = ClientMock()
        with patch("homeassistant.components.twinkly.Twinkly", return_value=mock):
            assert await async_setup_component(hass, DOMAIN, {})
            await hass.async_block_till_done()
        return mock

    return func
