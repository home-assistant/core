"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.backup import (
    DOMAIN,
    AgentBackup,
    BackupAgent,
    BackupAgentPlatformProtocol,
)
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import Backup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import MockPlatform, mock_platform

LOCAL_AGENT_ID = f"{DOMAIN}.local"

TEST_BACKUP_ABC123 = AgentBackup(
    backup_id="abc123",
    date="1970-01-01T00:00:00.000Z",
    name="Test",
    protected=False,
    size=0.0,
)
TEST_BACKUP_PATH_ABC123 = Path("abc123.tar")

TEST_BACKUP_DEF456 = AgentBackup(
    backup_id="def456",
    date="1980-01-01T00:00:00.000Z",
    name="Test 2",
    protected=False,
    size=1.0,
)

TEST_DOMAIN = "test"


class BackupAgentTest(BackupAgent):
    """Test backup agent."""

    def __init__(self, name: str, backups: list[AgentBackup] | None = None) -> None:
        """Initialize the backup agent."""
        self.name = name
        if backups is None:
            backups = [
                AgentBackup(
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
        backup: AgentBackup,
        homeassistant_version: str,
        **kwargs: Any,
    ) -> None:
        """Upload a backup."""
        self._backups[backup.backup_id] = backup

    async def async_list_backups(self, **kwargs: Any) -> list[AgentBackup]:
        """List backups."""
        return list(self._backups.values())

    async def async_get_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> AgentBackup | None:
        """Return a backup."""
        return self._backups.get(backup_id)

    async def async_delete_backup(
        self,
        backup_id: str,
        **kwargs: Any,
    ) -> None:
        """Delete a backup file."""


async def setup_backup_integration(
    hass: HomeAssistant,
    with_hassio: bool = False,
    configuration: ConfigType | None = None,
    *,
    backups: dict[str, list[Backup]] | None = None,
    remote_agents: list[str] | None = None,
) -> bool:
    """Set up the Backup integration."""
    with (
        patch("homeassistant.components.backup.is_hassio", return_value=with_hassio),
        patch(
            "homeassistant.components.backup.backup.is_hassio", return_value=with_hassio
        ),
    ):
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
        await hass.async_block_till_done()
        if with_hassio or not backups:
            return result

        for agent_id, agent_backups in backups.items():
            agent = hass.data[DATA_MANAGER].backup_agents[agent_id]
            agent._backups = {backups.backup_id: backups for backups in agent_backups}
            if agent_id == LOCAL_AGENT_ID:
                agent._loaded_backups = True

        return result
