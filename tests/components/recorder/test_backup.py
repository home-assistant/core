"""Test backup platform for the Recorder integration."""


from unittest.mock import patch

import pytest

from homeassistant.components.recorder.backup import async_post_backup, async_pre_backup
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from tests.common import async_init_recorder_component


async def test_async_pre_backup(hass: HomeAssistant) -> None:
    """Test pre backup."""
    await async_init_recorder_component(hass)

    with patch(
        "homeassistant.components.recorder.backup.Recorder.lock_database"
    ) as lock_mock:
        await async_pre_backup(hass)
        assert lock_mock.called


async def test_async_pre_backup_with_timeout(hass: HomeAssistant) -> None:
    """Test pre backup with timeout."""
    await async_init_recorder_component(hass)

    with patch(
        "homeassistant.components.recorder.backup.Recorder.lock_database",
        side_effect=TimeoutError(),
    ) as lock_mock, pytest.raises(TimeoutError):
        await async_pre_backup(hass)
        assert lock_mock.called


async def test_async_post_backup(hass: HomeAssistant) -> None:
    """Test post backup."""
    await async_init_recorder_component(hass)

    with patch(
        "homeassistant.components.recorder.backup.Recorder.unlock_database"
    ) as unlock_mock:
        await async_post_backup(hass)
        assert unlock_mock.called


async def test_async_post_backup_failure(hass: HomeAssistant) -> None:
    """Test post backup failure."""
    await async_init_recorder_component(hass)

    with patch(
        "homeassistant.components.recorder.backup.Recorder.unlock_database",
        return_value=False,
    ) as unlock_mock, pytest.raises(HomeAssistantError):
        await async_post_backup(hass)
        assert unlock_mock.called
