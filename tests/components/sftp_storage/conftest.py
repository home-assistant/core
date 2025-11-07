"""PyTest fixtures and test helpers."""

from collections.abc import Awaitable, Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from unittest.mock import patch

from asyncssh import generate_private_key
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
    DEFAULT_PKEY_NAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.setup import async_setup_component
from homeassistant.util.ulid import ulid

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
TEST_AGENT_ID = ulid()


@contextmanager
def private_key_file(hass: HomeAssistant) -> Generator[str]:
    """Fixture that create private key file in integration storage directory."""

    # Create private key file and parent directory.
    key_dest_path = Path(hass.config.path(STORAGE_DIR, DOMAIN))
    dest_file = key_dest_path / f".{ulid()}_{DEFAULT_PKEY_NAME}"
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to file only once.
    if not dest_file.exists():
        dest_file.write_bytes(
            generate_private_key("ssh-rsa").export_private_key("pkcs8-pem")
        )

    yield str(dest_file)

    if dest_file.exists():
        dest_file.unlink(missing_ok=True)
        with suppress(OSError):
            dest_file.parent.rmdir()


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_ssh_connection: SSHClientConnectionMock,
) -> ComponentSetup:
    """Fixture for setting up the component manually."""
    config_entry.add_to_hass(hass)

    async def func(config_entry: MockConfigEntry = config_entry) -> None:
        assert await async_setup_component(hass, BACKUP_DOMAIN, {})
        await hass.config_entries.async_setup(config_entry.entry_id)

    return func


@pytest.fixture(name="config_entry")
def mock_config_entry(hass: HomeAssistant) -> Generator[MockConfigEntry]:
    """Fixture for MockConfigEntry."""

    # pylint: disable-next=contextmanager-generator-missing-cleanup
    with private_key_file(hass) as private_key:
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=TEST_AGENT_ID,
            unique_id=TEST_AGENT_ID,
            title=CONFIG_ENTRY_TITLE,
            data={
                CONF_HOST: "127.0.0.1",
                CONF_PORT: 22,
                CONF_USERNAME: "username",
                CONF_PASSWORD: "password",
                CONF_PRIVATE_KEY_FILE: str(private_key),
                CONF_BACKUP_LOCATION: "backup_location",
            },
        )

        config_entry.runtime_data = SFTPConfigEntryData(**config_entry.data)
        yield config_entry


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
