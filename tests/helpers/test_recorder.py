"""The tests for the recorder helpers."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import recorder

from tests.common import SetupRecorderInstanceT


async def test_async_migration_in_progress(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
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
