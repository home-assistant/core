"""PyTest fixtures and test helpers."""

from collections.abc import AsyncIterator, Awaitable, Callable
from io import BytesIO
import tarfile
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.backup import DOMAIN as BACKUP_DOMAIN
from homeassistant.components.backup_sftp import SFTPConfigEntryData
from homeassistant.components.backup_sftp.const import (
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

from tests.common import MockConfigEntry

type ComponentSetup = Callable[[], Awaitable[None]]

CONFIG_ENTRY_TITLE = "testsshuser@127.0.0.1"
USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 22,
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PRIVATE_KEY_FILE: "private_key",
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


class AsyncFileIteratorMock:
    """Class that mocks `homeassistant.components.backup_sftp.client.AsyncFileIterator`."""

    def __init__(self, content: bytes) -> None:
        """Initialize `AsyncFileIteratorMock`."""
        self.content = BytesIO(content)

    def __aiter__(self) -> AsyncIterator[bytes]:
        """Initialize iteration."""
        return self

    async def __anext__(self) -> bytes:
        """Return next content in iteration."""
        chunk = self.content.read()
        if not chunk:
            try:
                self.content.close()
            finally:
                raise StopAsyncIteration
        return chunk


def create_tar_bytes(files: dict[str, str | bytes]) -> bytes:
    """Create an in-memory tar archive."""
    buf = BytesIO()
    with tarfile.open(mode="w", fileobj=buf) as tar:
        for name, content in files.items():
            if isinstance(content, str):
                content = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(content)
            tar.addfile(tarinfo=info, fileobj=BytesIO(content))
    return buf.getvalue()


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    ssh_objects: tuple[AsyncMock, AsyncMock],
) -> ComponentSetup:
    """Fixture for setting up the component manually."""
    config_entry.add_to_hass(hass)

    async def func() -> None:
        with (
            patch(
                "homeassistant.components.backup_sftp.client.connect",
                new_callable=AsyncMock,
            ) as _mock_connect,
            patch(
                "homeassistant.components.backup_sftp.client.SSHClientConnectionOptions",
                return_value=MagicMock(),
            ),
            NamedTemporaryFile() as tmpfile,
        ):
            user_input = USER_INPUT.copy()
            user_input[CONF_PRIVATE_KEY_FILE] = tmpfile.name

            _mock_connect.return_value = ssh_objects[0]
            assert await async_setup_component(hass, BACKUP_DOMAIN, {})
            await hass.config_entries.async_setup(config_entry.entry_id)
            await hass.async_block_till_done()

    return func


@pytest.fixture
def async_cm_mock() -> AsyncMock:
    """Test agent list backups."""
    mocked_client = AsyncMock()
    mocked_client.__aenter__ = AsyncMock(return_value=mocked_client)
    mocked_client.__aexit__ = AsyncMock(return_value=None)
    return mocked_client


@pytest.fixture
def async_cm_mock_generator() -> Callable[[], MagicMock]:
    """Return function that generates AsyncMock context manager."""

    def _generator() -> MagicMock:
        mocked_client = MagicMock()
        mocked_client.return_value.__aenter__ = AsyncMock(return_value=mocked_client)
        mocked_client.return_value.__aexit__ = AsyncMock(return_value=None)
        return mocked_client

    return _generator


@pytest.fixture
def fake_connect(async_cm_mock: AsyncMock) -> AsyncMock:
    """Prepare a fake `asyncssh.connect` cm to simulate a successful connection."""
    mck = AsyncMock()
    mck.__aenter__.return_value = mck
    mck.start_sftp_client = lambda: async_cm_mock
    return mck


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
            CONF_PRIVATE_KEY_FILE: "private_key",
            CONF_BACKUP_LOCATION: "backup_location",
        },
    )

    config_entry.runtime_data = SFTPConfigEntryData(**config_entry.data)
    return config_entry


@pytest.fixture
def ssh_objects() -> tuple[AsyncMock, AsyncMock]:
    """Return mocked objects returned by `asyncssh.connect` and `SSHClient.start_sftp_client`.

    Designed to remove warnings of non-awaited `close` and `exit` methods.
    """
    sshobject = AsyncMock()
    sftpobject = AsyncMock()

    sshobject.start_sftp_client.return_value = sftpobject
    sshobject.close = sftpobject.exit = MagicMock()
    return sshobject, sftpobject
