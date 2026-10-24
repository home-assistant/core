"""Common helpers for the Backup integration tests."""

from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Buffer,
    Callable,
    Coroutine,
    Generator,
    Iterable,
)
from contextlib import contextmanager
from io import StringIO
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient
from freezegun.api import FrozenDateTimeFactory
from pytest_homeassistant.common import async_fire_time_changed, mock_platform

from homeassistant.components.backup import (
    DOMAIN,
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentPlatformProtocol,
    BackupNotFound,
    Folder,
    UploadBackupEvent,
    async_get_manager,
)
from homeassistant.components.backup.backup import CoreLocalBackupAgent
from homeassistant.components.backup.const import BUF_SIZE, DATA_MANAGER
from homeassistant.components.backup.manager import (
    UPLOAD_PROGRESS_DEBOUNCE_SECONDS,
    ManagerStateEvent,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

LOCAL_AGENT_ID = f"{DOMAIN}.local"

TEST_BACKUP_ABC123 = AgentBackup(
    addons=[AddonInfo(name="Test", slug="test", version="1.0.0")],
    backup_id="abc123",
    database_included=True,
    date="1970-01-01T00:00:00.000Z",
    extra_metadata={"instance_id": "our_uuid", "with_automatic_settings": True},
    folders=[Folder.MEDIA, Folder.SHARE],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test",
    protected=False,
    size=0,
)
TEST_BACKUP_PATH_ABC123 = Path("abc123.tar")

TEST_BACKUP_DEF456 = AgentBackup(
    addons=[],
    backup_id="def456",
    database_included=False,
    date="1980-01-01T00:00:00.000Z",
    extra_metadata={"instance_id": "unknown_uuid", "with_automatic_settings": True},
    folders=[Folder.MEDIA, Folder.SHARE],
    homeassistant_included=True,
    homeassistant_version="2024.12.0",
    name="Test 2",
    protected=False,
    size=1,
)
TEST_BACKUP_PATH_DEF456 = Path("custom_def456.tar")

TEST_DOMAIN = "test"


async def aiter_from_iter(iterable: Iterable) -> AsyncIterator:
    """Convert an iterable to an async iterator."""
    for i in iterable:
        yield i


async def aiter_padded_chunks(data: bytes) -> AsyncGenerator[bytes]:
    """Yield data in chunks, followed by padding.

    The padding is larger than the buffer of tar readers, so the stream is not
    exhausted by readers which stop at the end of the tar archive.
    """
    for i in range(0, len(data), 1024):
        yield data[i : i + 1024]
    for _ in range(3):
        yield b"\0" * BUF_SIZE


def mock_download_from_file(
    mock_agent: Mock, path: Path
) -> list[AsyncGenerator[bytes]]:
    """Make an agent download a file, and return the opened download streams."""
    data = path.read_bytes()
    streams: list[AsyncGenerator[bytes]] = []

    async def download_backup(backup_id: str, **kwargs: Any) -> AsyncIterator[bytes]:
        """Mock download."""
        stream = aiter_padded_chunks(data)
        streams.append(stream)
        return stream

    mock_agent.async_download_backup.side_effect = download_backup
    return streams


def mock_backup_agent(name: str, backups: list[AgentBackup] | None = None) -> Mock:
    """Create a mock backup agent."""

    async def delete_backup(backup_id: str, **kwargs: Any) -> None:
        """Mock delete."""
        await get_backup(backup_id)

    async def download_backup(backup_id: str, **kwargs: Any) -> AsyncIterator[bytes]:
        """Mock download."""
        return aiter_from_iter((backups_data.get(backup_id, b"backup data"),))

    async def get_backup(backup_id: str, **kwargs: Any) -> AgentBackup:
        """Get a backup."""
        backup = next((b for b in _backups if b.backup_id == backup_id), None)
        if backup is None:
            raise BackupNotFound
        return backup

    async def upload_backup(
        *,
        open_stream: Callable[[], Coroutine[Any, Any, AsyncIterator[bytes]]],
        backup: AgentBackup,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        _backups.append(backup)
        backup_stream = await open_stream()
        backup_data = bytearray()
        async for chunk in backup_stream:
            backup_data += chunk
        backups_data[backup.backup_id] = backup_data

    _backups = backups or []
    backups_data: dict[str, Buffer] = {}
    mock_agent = Mock(spec=BackupAgent)
    mock_agent.domain = TEST_DOMAIN
    mock_agent.name = name
    mock_agent.unique_id = name
    type(mock_agent).agent_id = BackupAgent.agent_id
    mock_agent.async_delete_backup = AsyncMock(
        side_effect=delete_backup, spec_set=[BackupAgent.async_delete_backup]
    )
    mock_agent.async_download_backup = AsyncMock(
        side_effect=download_backup, spec_set=[BackupAgent.async_download_backup]
    )
    mock_agent.async_get_backup = AsyncMock(
        side_effect=get_backup, spec_set=[BackupAgent.async_get_backup]
    )
    mock_agent.async_list_backups = AsyncMock(
        return_value=_backups, spec_set=[BackupAgent.async_list_backups]
    )
    mock_agent.async_upload_backup = AsyncMock(
        side_effect=upload_backup,
        spec_set=[BackupAgent.async_upload_backup],
    )
    return mock_agent


async def setup_backup_integration(
    hass: HomeAssistant,
    with_hassio: bool = False,
    *,
    backups: dict[str, list[AgentBackup]] | None = None,
    remote_agents: list[str] | None = None,
) -> dict[str, Mock]:
    """Set up the Backup integration."""
    backups = backups or {}
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=with_hassio),
        patch(
            "homeassistant.components.backup.backup.is_hassio", return_value=with_hassio
        ),
        patch(
            "homeassistant.components.backup.services.is_hassio",
            return_value=with_hassio,
        ),
    ):
        remote_agents = remote_agents or []
        remote_agents_dict = {}
        for agent in remote_agents:
            if not agent.startswith(f"{TEST_DOMAIN}."):
                raise ValueError(f"Invalid agent_id: {agent}")
            name = agent.partition(".")[2]
            remote_agents_dict[agent] = mock_backup_agent(name, backups.get(agent))
        if remote_agents:
            platform = Mock(
                async_get_backup_agents=AsyncMock(
                    return_value=list(remote_agents_dict.values())
                ),
                spec_set=BackupAgentPlatformProtocol,
            )
            await setup_backup_platform(hass, domain=TEST_DOMAIN, platform=platform)

        assert await async_setup_component(hass, DOMAIN, {})
        # The config entry is set up from a background discovery flow.
        await hass.async_block_till_done(wait_background_tasks=True)

        if LOCAL_AGENT_ID not in backups or with_hassio:
            return remote_agents_dict

        local_agent = cast(
            CoreLocalBackupAgent, hass.data[DATA_MANAGER].backup_agents[LOCAL_AGENT_ID]
        )

        for backup in backups[LOCAL_AGENT_ID]:
            await local_agent.async_upload_backup(
                open_stream=AsyncMock(
                    side_effect=RuntimeError("Local agent does not open stream")
                ),
                backup=backup,
                on_progress=lambda *, on_progress, **_: None,
            )
        local_agent._loaded_backups = True

        return remote_agents_dict


async def setup_backup_platform(
    hass: HomeAssistant,
    *,
    domain: str,
    platform: Any,
) -> None:
    """Set up a mock domain."""
    mock_platform(hass, f"{domain}.backup", platform)
    assert await async_setup_component(hass, domain, {})
    await hass.async_block_till_done()


async def upload_backup_via_http(
    client: TestClient,
    agent_id: str,
    backup: AgentBackup,
    chunks: Iterable[bytes] = (b"test",),
) -> ClientResponse:
    """Upload a backup to an agent through the backup upload view.

    The manager reads the uploaded backup as `backup` and streams it to the
    agent as `chunks`, one stream chunk per item.
    """
    with (
        patch(
            "homeassistant.components.backup.manager.BackupManager.async_get_backup",
            return_value=backup,
        ),
        patch(
            "homeassistant.components.backup.manager.read_backup",
            return_value=backup,
        ),
        patch("pathlib.Path.open") as mocked_open,
    ):
        mocked_open.return_value.read = Mock(side_effect=[*chunks, b""])
        return await client.post(
            f"/api/backup/upload?agent_id={agent_id}",
            data={"file": StringIO("test")},
        )


@contextmanager
def collect_upload_events(
    hass: HomeAssistant, agent_id: str
) -> Generator[list[UploadBackupEvent]]:
    """Collect the upload events of an agent while the context is active."""
    events: list[UploadBackupEvent] = []

    @callback
    def _collect(event: ManagerStateEvent) -> None:
        if isinstance(event, UploadBackupEvent) and event.agent_id == agent_id:
            events.append(event)

    unsub = async_get_manager(hass).async_subscribe_events(_collect)
    try:
        yield events
    finally:
        unsub()


@callback
def flush_upload_progress(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """End the cooldown of the manager's upload progress debouncer.

    Call it between two progress reports of an agent, so both are emitted as
    upload events.
    """
    freezer.tick(UPLOAD_PROGRESS_DEBOUNCE_SECONDS)
    async_fire_time_changed(hass)
