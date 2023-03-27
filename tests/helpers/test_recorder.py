"""The tests for the recorder helpers."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder

from tests.typing import RecorderInstanceGenerator


async def test_async_migration_in_progress(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test async_migration_in_progress wraps the recorder."""
    with patch(
        "homeassistant.components.recorder.util.async_migration_in_progress",
        return_value=False,
    ):
        assert recorder.async_migration_in_progress(hass) is False

    # The recorder is not loaded
    with patch(
        "homeassistant.components.recorder.util.async_migration_in_progress",
        return_value=True,
    ):
        assert recorder.async_migration_in_progress(hass) is False

    await async_setup_recorder_instance(hass)

    # The recorder is now loaded
    with patch(
        "homeassistant.components.recorder.util.async_migration_in_progress",
        return_value=True,
    ):
        assert recorder.async_migration_in_progress(hass) is True
