"""Common helpers for the Backup integration tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from homeassistant.components.backup import DOMAIN
from homeassistant.components.backup.agent import BackupAgent, UploadedBackup
from homeassistant.components.backup.manager import Backup
from homeassistant.components.backup.models import BackupUploadMetadata
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

TEST_BACKUP = Backup(
    slug="abc123",
    name="Test",
    date="1970-01-01T00:00:00.000Z",
    path=Path("abc123.tar"),
    size=0.0,
)


class BackupAgentTest(BackupAgent):
    """Test backup agent."""

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
                name="Test",
                slug="abc123",
                size=13.37,
                date="1970-01-01T00:00:00Z",
            )
        ]


async def setup_backup_integration(
    hass: HomeAssistant,
    with_hassio: bool = False,
    configuration: ConfigType | None = None,
) -> bool:
    """Set up the Backup integration."""
    with patch("homeassistant.components.backup.is_hassio", return_value=with_hassio):
        return await async_setup_component(hass, DOMAIN, configuration or {})
