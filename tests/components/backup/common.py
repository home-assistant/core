"""Common helpers for the Backup integration tests."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from spencerassistant.components.backup import DOMAIN
from spencerassistant.components.backup.manager import Backup
from spencerassistant.core import spencerAssistant
from spencerassistant.helpers.typing import ConfigType
from spencerassistant.setup import async_setup_component

TEST_BACKUP = Backup(
    slug="abc123",
    name="Test",
    date="1970-01-01T00:00:00.000Z",
    path=Path("abc123.tar"),
    size=0.0,
)


async def setup_backup_integration(
    hass: spencerAssistant,
    with_hassio: bool = False,
    configuration: ConfigType | None = None,
) -> bool:
    """Set up the Backup integration."""
    with patch("spencerassistant.components.backup.is_hassio", return_value=with_hassio):
        return await async_setup_component(hass, DOMAIN, configuration or {})
