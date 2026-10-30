"""Tests for the Plex diagnostics."""

from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.plex.const import DOMAIN
from homeassistant.components.plex.server import PlexServer
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DEFAULT_DATA, DEFAULT_OPTIONS


@pytest.mark.parametrize(
    "options",
    [
        pytest.param(DEFAULT_OPTIONS, id="saved_users"),
        pytest.param({Platform.MEDIA_PLAYER: {}}, id="no_saved_users"),
        pytest.param(
            {
                Platform.MEDIA_PLAYER: {
                    "ignore_new_shared_users": False,
                    "monitored_users": {"User 1": {"enabled": False}},
                }
            },
            id="new_shared_users",
        ),
        pytest.param(
            {
                Platform.MEDIA_PLAYER: {
                    "ignore_new_shared_users": True,
                    "monitored_users": {"User 1": {"enabled": True}},
                }
            },
            id="ignore_new_shared_users",
        ),
    ],
)
async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_plex_server: Callable[..., Awaitable[PlexServer]],
    mock_websocket: MagicMock,
    snapshot: SnapshotAssertion,
    options: dict[str, Any],
) -> None:
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=options,
        unique_id=DEFAULT_DATA["server_id"],
    )
    await setup_plex_server(config_entry=entry)
    mock_websocket.return_value.state = "connected"

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
