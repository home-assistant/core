"""Tests for the Backup integration."""
from unittest.mock import patch

import pytest

from spencerassistant.components.backup.const import DOMAIN
from spencerassistant.core import spencerAssistant

from .common import setup_backup_integration


async def test_setup_with_hassio(
    hass: spencerAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the setup of the integration with hassio enabled."""
    assert not await setup_backup_integration(hass=hass, with_hassio=True)
    assert (
        "The backup integration is not supported on this installation method, please remove it from your configuration"
        in caplog.text
    )


async def test_create_service(
    hass: spencerAssistant,
) -> None:
    """Test generate backup."""
    await setup_backup_integration(hass)

    with patch(
        "spencerassistant.components.backup.websocket.BackupManager.generate_backup",
    ) as generate_backup:
        await hass.services.async_call(
            DOMAIN,
            "create",
            blocking=True,
        )

    assert generate_backup.called
