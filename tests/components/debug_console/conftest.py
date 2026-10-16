"""Fixtures for the Debug console tests."""

from typing import Any

import pytest

from homeassistant.components.debug_console.const import (
    CONF_WARNING_ACCEPTED,
    DOMAIN,
    WARNING_VERSION,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockUser
from tests.typing import MockHAClientWebSocket, WebSocketGenerator


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, hass_storage: dict[str, Any], hass_admin_user: MockUser
) -> None:
    """Set up the Debug console, with the warning accepted by the admin."""
    hass_storage[DOMAIN] = {
        "version": 1,
        "key": DOMAIN,
        "data": {
            CONF_WARNING_ACCEPTED: {
                hass_admin_user.id: {
                    "version": WARNING_VERSION,
                    "accepted_at": "2026-01-01T00:00:00+00:00",
                }
            }
        },
    }
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})


@pytest.fixture
async def websocket_client(
    hass: HomeAssistant,
    setup_integration: None,
    hass_ws_client: WebSocketGenerator,
) -> MockHAClientWebSocket:
    """Create a websocket client, with the Debug console set up."""
    return await hass_ws_client(hass)
