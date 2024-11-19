"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.backup import (
    DOMAIN,
    BackupAgent,
    BackupAgentPlatformProtocol,
    BackupUploadMetadata,
    BaseBackup,
)
from homeassistant.components.backup.backup import LocalBackup
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import Backup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, mock_platform

LOCAL_AGENT_ID = f"{DOMAIN}.local"

TEST_BASE_BACKUP_ABC123 = BaseBackup(
    backup_id="abc123",
    date="1970-01-01T00:00:00.000Z",
    name="Test",
    protected=False,
    size=0.0,
)
TEST_BACKUP_PATH_ABC123 = Path("abc123.tar")
TEST_LOCAL_BACKUP_ABC123 = LocalBackup(
    date="1970-01-01T00:00:00.000Z",
    backup_id="abc123",
    name="Test",
    path=Path("abc123.tar"),
    protected=False,
    size=0.0,
)

TEST_BASE_BACKUP_DEF456 = BaseBackup(
    backup_id="def456",
    date="1980-01-01T00:00:00.000Z",
    name="Test 2",
    protected=False,
    size=1.0,
)

TEST_DOMAIN = "test"


class BackupAgentTest(BackupAgent):
    """Test backup agent."""

    def __init__(self, name: str, backups: list[BaseBackup] | None = None) -> None:
        """Initialize the backup agent."""
        self.name = name
        if backups is None:
            backups = [
                BaseBackup(
                    backup_id="abc123",
                    date="1970-01-01T00:00:00Z",
                    name="Test",
                    protected=False,
                    size=13.37,
                )
            ]

        self._backups = {backup.backup_id: backup for backup in backups}

    async def async_download_backup(
        self,
        backup_id: str,
        *,
        path: Path,
        **kwargs: Any,
    ) -> None:
        """Download a backup file."""

    async def async_upload_backup(
        self,
        *,
        path: Path,
        metadata: BackupUploadMetadata,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        self._backups[metadata.backup_id] = BaseBackup(
            backup_id=metadata.backup_id,
            date=metadata.date,
            name=metadata.name,
            protected=metadata.protected,
            size=metadata.size,
        )

    async def async_list_backups(self, **kwargs: Any) -> list[BaseBackup]:
        """List backups."""
        return list(self._backups.values())

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> BaseBackup | None:
        """Return a backup."""
        return self._backups.get(backup_id)


async def setup_backup_integration(
    hass: HomeAssistant,
    with_hassio: bool = False,
    configuration: ConfigType | None = None,
    *,
    backups: dict[str, list[Backup]] | None = None,
    remote_agents: list[str] | None = None,
) -> bool:
    """Set up the Backup integration."""
    with patch("homeassistant.components.backup.is_hassio", return_value=with_hassio):
        remote_agents = remote_agents or []
        platform = Mock(
            async_get_backup_agents=AsyncMock(
                return_value=[BackupAgentTest(agent, []) for agent in remote_agents]
            ),
            spec_set=BackupAgentPlatformProtocol,
        )

        mock_platform(hass, f"{TEST_DOMAIN}.backup", platform or MockPlatform())
        assert await async_setup_component(hass, TEST_DOMAIN, {})

        result = await async_setup_component(hass, DOMAIN, configuration or {})
        if with_hassio or not backups:
            return result

        for agent_id, agent_backups in backups.items():
            agent = hass.data[DATA_MANAGER].backup_agents[agent_id]
            agent._backups = {backups.backup_id: backups for backups in agent_backups}
            if agent_id == LOCAL_AGENT_ID:
                agent._loaded_backups = True

        return result
