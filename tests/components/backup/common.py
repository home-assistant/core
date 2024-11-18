"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.components.backup import (
    DOMAIN,
    BackupAgent,
    BackupUploadMetadata,
    UploadedBackup,
)
from homeassistant.components.backup.backup import LocalBackup
from homeassistant.components.backup.const import DATA_MANAGER
from homeassistant.components.backup.manager import LOCAL_AGENT_ID, Backup
from homeassistant.components.backup.models import BaseBackup
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

TEST_BASE_BACKUP = BaseBackup(
    slug="abc123",
    name="Test",
    date="1970-01-01T00:00:00.000Z",
    size=0.0,
    protected=False,
)
TEST_BACKUP = Backup(
    agent_ids=["backup.local"],
    slug="abc123",
    name="Test",
    date="1970-01-01T00:00:00.000Z",
    size=0.0,
    protected=False,
)
TEST_BACKUP_PATH = Path("abc123.tar")
TEST_LOCAL_BACKUP = LocalBackup(
    id="abc123",
    slug="abc123",
    name="Test",
    date="1970-01-01T00:00:00.000Z",
    path=Path("abc123.tar"),
    size=0.0,
    protected=False,
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

    async def async_list_backups(self, **kwargs: Any) -> list[UploadedBackup]:
        """List backups."""
        return [
            UploadedBackup(
                id="abc123",
                date="1970-01-01T00:00:00Z",
                name="Test",
                protected=False,
                size=13.37,
                slug="abc123",
            )
        ]

    async def async_get_backup(
        self,
        *,
        slug: str,
        **kwargs: Any,
    ) -> UploadedBackup | None:
        """Return a backup."""
        if slug != "abc123":
            return None
        return UploadedBackup(
            id="abc123",
            date="1970-01-01T00:00:00Z",
            name="Test",
            protected=False,
            size=13.37,
            slug="abc123",
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
        local_agent._backups = {backups.slug: backups for backups in backups}
        local_agent._loaded_backups = True

        return result
