"""Fixtures for the Debug console tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(autouse=True)
def no_automatic_enabling() -> Generator[None]:
    """Do not let development versions enable the console by themselves."""
    with patch("homeassistant.components.debug_console.IS_DEVELOPMENT_VERSION", False):
        yield


@pytest.fixture
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the Debug console, enabled by its config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant, setup_integration: None, hass_ws_client: WebSocketGenerator
) -> MockHAClientWebSocket:
    """Create a websocket client, with the Debug console set up."""
    return await hass_ws_client(hass)
