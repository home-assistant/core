"""The tests for the recorder helpers."""

from unittest.mock import patch

from spencerassistant.core import spencerAssistant
from spencerassistant.helpers import recorder

from tests.common import SetupRecorderInstanceT


async def test_async_migration_in_progress(
    async_setup_recorder_instance: SetupRecorderInstanceT, hass: spencerAssistant
):
    """Test async_migration_in_progress wraps the recorder."""
    with patch(
        "spencerassistant.components.recorder.util.async_migration_in_progress",
        return_value=False,
    ):
        assert recorder.async_migration_in_progress(hass) is False

    # The recorder is not loaded
    with patch(
        "spencerassistant.components.recorder.util.async_migration_in_progress",
        return_value=True,
    ):
        assert recorder.async_migration_in_progress(hass) is False

    await async_setup_recorder_instance(hass)

    # The recorder is now loaded
    with patch(
        "spencerassistant.components.recorder.util.async_migration_in_progress",
        return_value=True,
    ):
        assert recorder.async_migration_in_progress(hass) is True
