"""PyTest fixtures and test helpers."""

from collections.abc import Awaitable, Callable
from unittest.mock import patch

import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN, AgentBackup
from homeassistant.components.sftp_storage import SFTPConfigEntryData
from homeassistant.components.sftp_storage.const import (
    CONF_BACKUP_LOCATION,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_PRIVATE_KEY_FILE,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from .asyncssh_mock import SSHClientConnectionMock, async_context_manager

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]

BACKUP_METADATA = {
    "file_path": "backup_location/backup.tar",
    "metadata": {
        "addons": [{"name": "Test", "slug": "test", "version": "1.0.0"}],
        "backup_id": "test-backup",
        "date": "2025-01-01T01:23:45.687000+01:00",
        "database_included": True,
        "extra_metadata": {
            "instance_id": 1,
            "with_automatic_settings": False,
            "supervisor.backup_request_date": "2025-01-01T01:23:45.687000+01:00",
        },
        "folders": [],
        "homeassistant_included": True,
        "homeassistant_version": "2024.12.0",
        "name": "Test",
        "protected": True,
        "size": 1234,
    },
}
TEST_AGENT_BACKUP = AgentBackup.from_dict(BACKUP_METADATA["metadata"])

CONFIG_ENTRY_TITLE = "testsshuser@127.0.0.1"
PRIVATE_KEY_FILE_UUID = "0123456789abcdef0123456789abcdef"
USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 22,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PRIVATE_KEY_FILE: PRIVATE_KEY_FILE_UUID,
    CONF_BACKUP_LOCATION: "backup_location",
}
TEST_AGENT_ID = slugify(
    ".".join(
        [
            USER_INPUT[CONF_HOST],
            str(USER_INPUT[CONF_PORT]),
            USER_INPUT[CONF_USERNAME],
            USER_INPUT[CONF_BACKUP_LOCATION],
        ]
    )
)


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ssh_connection: SSHClientConnectionMock,
) -> ComponentSetup:
    """Fixture for setting up the component manually."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return func


@pytest.fixture(name="config_entry")
def mock_config_entry() -> MockConfigEntry:
    """Fixture for MockConfigEntry."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_AGENT_ID,
        title=CONFIG_ENTRY_TITLE,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 22,
            CONF_USERNAME: "username",
            CONF_PASSWORD: "password",
            CONF_PRIVATE_KEY_FILE: "/path/to/private_key",
            CONF_BACKUP_LOCATION: "backup_location",
        },
    )

    config_entry.runtime_data = SFTPConfigEntryData(**config_entry.data)
    return config_entry


@pytest.fixture
def mock_ssh_connection():
    """Mock `SSHClientConnection` globally."""
    mock = SSHClientConnectionMock()

    # We decorate from same decorator from asyncssh
    # It makes the callable an awaitable and context manager.
    @async_context_manager
    async def mock_connect(*args, **kwargs):
        """Mock the asyncssh.connect function to return our mock directly."""
        return mock

    with (
        patch(
            "homeassistant.components.sftp_storage.client.connect",
            side_effect=mock_connect,
        ),
        patch(
            "homeassistant.components.sftp_storage.config_flow.connect",
            side_effect=mock_connect,
        ),
    ):
        yield mock
