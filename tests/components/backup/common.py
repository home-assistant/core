"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.components.backup import (
    DOMAIN,
    BackupAgent,
    BackupUploadMetadata,
    BaseBackup,
)
from homeassistant.components.backup.backup import LocalBackup
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import Backup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

LOCAL_AGENT_ID = f"{DOMAIN}.local"

TEST_BASE_BACKUP = BaseBackup(
    backup_id="abc123",
    date="1970-01-01T00:00:00.000Z",
    name="Test",
    protected=False,
    size=0.0,
)
TEST_BACKUP = Backup(
    agent_ids=["backup.local"],
    backup_id="abc123",
    date="1970-01-01T00:00:00.000Z",
    name="Test",
    protected=False,
    size=0.0,
)
TEST_BACKUP_PATH = Path("abc123.tar")
TEST_LOCAL_BACKUP = LocalBackup(
    date="1970-01-01T00:00:00.000Z",
    backup_id="abc123",
    name="Test",
    path=Path("abc123.tar"),
    protected=False,
    size=0.0,
)


class BackupAgentTest(BackupAgent):
    """Test backup agent."""

    def __init__(self, name: str) -> None:
        """Initialize the backup agent."""
        self.name = name

    async def async_download_backup(
        self,
        *,
        id: str,
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

    async def async_list_backups(self, **kwargs: Any) -> list[BaseBackup]:
        """List backups."""
        return [
            BaseBackup(
                backup_id="abc123",
                date="1970-01-01T00:00:00Z",
                name="Test",
                protected=False,
                size=13.37,
            )
        ]

    async def async_get_backup(
        self,
        *,
        backup_id: str,
        **kwargs: Any,
    ) -> BaseBackup | None:
        """Return a backup."""
        if backup_id != "abc123":
            return None
        return BaseBackup(
            backup_id="abc123",
            date="1970-01-01T00:00:00Z",
            name="Test",
            protected=False,
            size=13.37,
        )


async def setup_backup_integration(
    hass: HomeAssistant,
    with_hassio: bool = False,
    configuration: ConfigType | None = None,
    backups: list[Backup] | None = None,
) -> bool:
    """Set up the Backup integration."""
    with patch("homeassistant.components.backup.is_hassio", return_value=with_hassio):
        result = await async_setup_component(hass, DOMAIN, configuration or {})
        if with_hassio or not backups:
            return result

        local_agent = hass.data[DATA_MANAGER].backup_agents[LOCAL_AGENT_ID]
        local_agent._backups = {backup.backup_id: backup for backup in backups}
        local_agent._loaded_backups = True

        return result
