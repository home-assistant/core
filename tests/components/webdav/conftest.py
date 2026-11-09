"""Common fixtures for the WebDAV tests."""

from collections.abc import AsyncIterator, Generator
from json import dumps
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.webdav.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME

from .const import BACKUP_METADATA, MOCK_LIST_FILES


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.webdav.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )


async def _iter_read_mock(path: str, timeout=None) -> AsyncIterator[bytes]:
    """Mock the streaming download function."""
    yield b"backup "
    yield b"data"


@pytest.fixture(name="webdav_client")
def mock_webdav_client() -> Generator[AsyncMock]:
    """Mock the aiowebdav client."""
    with (
        patch(
            "homeassistant.components.webdav.helpers.Client",
            autospec=True,
        ) as mock_webdav_client,
    ):
        mock = mock_webdav_client.return_value
        mock.exists.return_value = True
        mock.mkdir.return_value = None
        mock.list.return_value = MOCK_LIST_FILES
        mock.iter_read.side_effect = _iter_read_mock
        mock.read.return_value = dumps(BACKUP_METADATA).encode()
        mock.write.return_value = None
        mock.delete.return_value = None
        yield mock
