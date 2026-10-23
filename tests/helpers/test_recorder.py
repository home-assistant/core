"""The tests for the recorder helpers."""

from unittest.mock import patch

from pytest_homeassistant.typing import RecorderInstanceGenerator

from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder


async def test_async_migration_in_progress(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test async_migration_in_progress wraps the recorder."""
    with patch(
        "homeassistant.components.recorder.util.async_migration_in_progress",
        return_value=False,
    ):
        assert recorder.async_migration_in_progress(hass) is False

    with patch(
        "homeassistant.components.recorder.util.async_migration_in_progress",
        return_value=True,
    ):
        assert recorder.async_migration_in_progress(hass) is True


async def test_async_migration_is_live(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test async_migration_in_progress wraps the recorder."""
    with patch(
        "homeassistant.components.recorder.util.async_migration_is_live",
        return_value=False,
    ):
        assert recorder.async_migration_is_live(hass) is False

    with patch(
        "homeassistant.components.recorder.util.async_migration_is_live",
        return_value=True,
    ):
        assert recorder.async_migration_is_live(hass) is True
