"""Test backup platform for the Recorder integration."""


from unittest.mock import patch

import pytest

from spencerassistant.components.recorder.backup import async_post_backup, async_pre_backup
from spencerassistant.core import spencerAssistant
from spencerassistant.exceptions import spencerAssistantError


async def test_async_pre_backup(recorder_mock, hass: spencerAssistant) -> None:
    """Test pre backup."""
    with patch(
        "spencerassistant.components.recorder.core.Recorder.lock_database"
    ) as lock_mock:
        await async_pre_backup(hass)
        assert lock_mock.called


async def test_async_pre_backup_with_timeout(
    recorder_mock, hass: spencerAssistant
) -> None:
    """Test pre backup with timeout."""
    with patch(
        "spencerassistant.components.recorder.core.Recorder.lock_database",
        side_effect=TimeoutError(),
    ) as lock_mock, pytest.raises(TimeoutError):
        await async_pre_backup(hass)
        assert lock_mock.called


async def test_async_pre_backup_with_migration(
    recorder_mock, hass: spencerAssistant
) -> None:
    """Test pre backup with migration."""
    with patch(
        "spencerassistant.components.recorder.backup.async_migration_in_progress",
        return_value=True,
    ), pytest.raises(spencerAssistantError):
        await async_pre_backup(hass)


async def test_async_post_backup(recorder_mock, hass: spencerAssistant) -> None:
    """Test post backup."""
    with patch(
        "spencerassistant.components.recorder.core.Recorder.unlock_database"
    ) as unlock_mock:
        await async_post_backup(hass)
        assert unlock_mock.called


async def test_async_post_backup_failure(recorder_mock, hass: spencerAssistant) -> None:
    """Test post backup failure."""
    with patch(
        "spencerassistant.components.recorder.core.Recorder.unlock_database",
        return_value=False,
    ) as unlock_mock, pytest.raises(spencerAssistantError):
        await async_post_backup(hass)
        assert unlock_mock.called
