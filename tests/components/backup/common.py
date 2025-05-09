"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from collections.abc import AsyncIterator, Buffer, Callable, Coroutine, Iterable
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.backup import (
    DOMAIN,
    AddonInfo,
    AgentBackup,
    BackupAgent,
    BackupAgentPlatformProtocol,
    BackupNotFound,
    Folder,
)
from homeassistant.components.backup.backup import CoreLocalBackupAgent
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.core import HomeAssistant
from homeassistant.helpers.backup import async_initialize_backup
from homeassistant.setup import async_setup_component

from tests.common import mock_platform

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
    async_initialize_backup(hass)
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=with_hassio),
        patch(
            "homeassistant.components.backup.backup.is_hassio", return_value=with_hassio
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
        await hass.async_block_till_done()

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
