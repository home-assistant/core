"""Fixtures for the Debug console tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(autouse=True)
def default_version() -> Generator[None]:
    """Run as a development version, but without enabling the console itself.

    Each module reads the version on import, so each one is patched. Tests of
    the safeguards of release versions patch it again.
    """
    with (
        patch("homeassistant.components.debug_console.IS_DEVELOPMENT_VERSION", False),
        patch(
            "homeassistant.components.debug_console.safeguards.IS_DEVELOPMENT_VERSION",
            True,
        ),
    ):
        yield


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the config entry that enables the Debug console."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up the Debug console, enabled by its config entry."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    return config_entry


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> MockHAClientWebSocket:
    """Create a websocket client, with the Debug console set up."""
    return await hass_ws_client(hass)
