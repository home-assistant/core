"""Test backup platform for the Recorder integration."""
from unittest.mock import patch

import pytest

from homeassistant.components import recorder
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_async_pre_backup(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test pre backup."""
    with patch(
        "homeassistant.components.recorder.core.Recorder.lock_database"
    ) as lock_mock:
        await recorder.backup.async_pre_backup(hass)
        assert lock_mock.called


async def test_async_pre_backup_with_timeout(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test pre backup with timeout."""
    with patch(
        "homeassistant.components.recorder.core.Recorder.lock_database",
        side_effect=TimeoutError(),
    ) as lock_mock, pytest.raises(TimeoutError):
        await recorder.backup.async_pre_backup(hass)
        assert lock_mock.called


async def test_async_pre_backup_with_migration(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test pre backup with migration."""
    with patch(
        "homeassistant.components.recorder.backup.async_migration_in_progress",
        return_value=True,
    ), pytest.raises(HomeAssistantError):
        await recorder.backup.async_pre_backup(hass)


async def test_async_post_backup(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test post backup."""
    with patch(
        "homeassistant.components.recorder.core.Recorder.unlock_database"
    ) as unlock_mock:
        await recorder.backup.async_post_backup(hass)
        assert unlock_mock.called


async def test_async_post_backup_failure(
    recorder_mock: recorder.Recorder, hass: HomeAssistant
) -> None:
    """Test post backup failure."""
    with patch(
        "homeassistant.components.recorder.core.Recorder.unlock_database",
        return_value=False,
    ) as unlock_mock, pytest.raises(HomeAssistantError):
        await recorder.backup.async_post_backup(hass)
        assert unlock_mock.called
