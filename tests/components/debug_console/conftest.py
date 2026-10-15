"""Fixtures for the Debug console tests."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.components.debug_console.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture(autouse=True)
def default_version() -> Generator[None]:
    """Run as a release version, but without the safeguards of one.

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
async def setup_integration(hass: HomeAssistant) -> None:
    """Set up the Debug console, enabled in YAML."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
) -> MockHAClientWebSocket:
    """Create a websocket client, with the Debug console set up."""
    return await hass_ws_client(hass)
