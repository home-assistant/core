"""Fixtures for the Kodi tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from jsonrpc_base.jsonrpc import TransportError
from pykodi.kodi import KodiHTTPConnection, KodiWSConnection
import pytest

from homeassistant.components.kodi.const import CONF_WS_PORT, DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from .util import UUID

from tests.common import MockConfigEntry

APPLICATION_PROPERTIES: dict[str, Any] = {
    "version": {"major": 21, "minor": 2},
    "volume": 80,
    "muted": False,
}


@pytest.fixture
def unique_id() -> str | None:
    """Return the unique ID of the config entry."""
    return UUID


@pytest.fixture
def mock_config_entry(unique_id: str | None) -> MockConfigEntry:
    """Return a Kodi config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="name",
        entry_id="01JZ8Y6K9QW3X5V7T2R4P6N8M0",
        unique_id=unique_id,
        data={
            CONF_NAME: "name",
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 8080,
            CONF_WS_PORT: 9090,
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            CONF_SSL: False,
        },
    )


@pytest.fixture
def can_subscribe() -> bool:
    """Return whether the connection pushes notifications (websocket)."""
    return False


@pytest.fixture
def mock_connection(can_subscribe: bool) -> Generator[MagicMock]:
    """Return a connected Kodi connection."""
    connection = MagicMock(
        spec=KodiWSConnection if can_subscribe else KodiHTTPConnection
    )
    connection.connected = True
    connection.can_subscribe = can_subscribe
    with patch(
        "homeassistant.components.kodi.get_kodi_connection",
        return_value=connection,
    ):
        yield connection


@pytest.fixture
def mock_kodi(mock_connection: MagicMock) -> Generator[MagicMock]:
    """Return a Kodi client without active players."""

    def get_application_properties(properties: list[str]) -> dict[str, Any]:
        if not mock_connection.connected:
            raise TransportError("Not connected")
        return {key: APPLICATION_PROPERTIES[key] for key in properties}

    with patch("homeassistant.components.kodi.Kodi", autospec=True) as kodi_class:
        kodi = kodi_class.return_value
        kodi.get_application_properties.side_effect = get_application_properties
        kodi.get_players.return_value = []
        kodi.thumbnail_url.return_value = "http://1.1.1.1:8080/image/thumbnail"
        yield kodi
