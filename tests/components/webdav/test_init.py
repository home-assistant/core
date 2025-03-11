"""Test WebDAV component setup."""

from unittest.mock import AsyncMock

from aiowebdav2.exceptions import WebDavError
import pytest

from homeassistant.components.webdav.const import CONF_BACKUP_PATH, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_migrate_wrong_path(
    hass: HomeAssistant, webdav_client: AsyncMock
) -> None:
    """Test migration of wrong encoded folder path."""
    webdav_client.list_with_properties.return_value = [
        {"/wrong%20path": []},
    ]

    config_entry = MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/wrong path",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )
    await setup_integration(hass, config_entry)

    webdav_client.move.assert_called_once_with("/wrong%20path", "/wrong path")


async def test_migrate_non_wrong_path(
    hass: HomeAssistant, webdav_client: AsyncMock
) -> None:
    """Test no migration of correct folder path."""
    webdav_client.list_with_properties.return_value = [
        {"/correct path": []},
    ]
    webdav_client.check.side_effect = lambda path: path == "/correct path"

    config_entry = MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/correct path",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )

    await setup_integration(hass, config_entry)

    webdav_client.move.assert_not_called()


async def test_migrate_error(
    hass: HomeAssistant,
    webdav_client: AsyncMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test migration of wrong encoded folder path with error."""
    webdav_client.list_with_properties.return_value = [
        {"/wrong%20path": []},
    ]
    webdav_client.move.side_effect = WebDavError("Failed to move")

    config_entry = MockConfigEntry(
        title="user@webdav.demo",
        domain=DOMAIN,
        data={
            CONF_URL: "https://webdav.demo",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "supersecretpassword",
            CONF_BACKUP_PATH: "/wrong path",
        },
        entry_id="01JKXV07ASC62D620DGYNG2R8H",
    )
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        'Failed to migrate wrong encoded folder "/wrong%20path" to "/wrong path"'
        in caplog.text
    )
