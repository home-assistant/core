"""The tests for the recorder helpers."""

from unittest.mock import patch

from homeassistant.helpers import recorder

from tests.common import async_init_recorder_component


async def test_async_migration_in_progress(hass):
    """Test async_migration_in_progress wraps the recorder."""
    with patch(
        "homeassistant.components.recorder.async_migration_in_progress",
        return_value=False,
    ):
        assert await recorder.async_migration_in_progress(hass) is False

    # The recorder is not loaded
    with patch(
        "homeassistant.components.recorder.async_migration_in_progress",
        return_value=True,
    ):
        assert await recorder.async_migration_in_progress(hass) is False

    await async_init_recorder_component(hass)

    # The recorder is now loaded
    with patch(
        "homeassistant.components.recorder.async_migration_in_progress",
        return_value=True,
    ):
        assert await recorder.async_migration_in_progress(hass) is True
