"""Test the Backblaze B2 storage integration."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from b2sdk.v2 import exception
import pytest

from homeassistant.components.backblaze_b2.const import CONF_APPLICATION_KEY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state == ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED  # type: ignore[comparison-overlap]


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry with invalid auth."""
    mock_config = MockConfigEntry(
        entry_id=mock_config_entry.entry_id,
        title=mock_config_entry.title,
        domain=mock_config_entry.domain,
        data={
            **mock_config_entry.data,
            CONF_APPLICATION_KEY: "invalid_key_id",
        },
    )

    await setup_integration(hass, mock_config)

    assert mock_config.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (exception.Unauthorized("msg", "code"), ConfigEntryState.SETUP_ERROR),
        (exception.RestrictedBucket("testBucket"), ConfigEntryState.SETUP_RETRY),
        (exception.NonExistentBucket(), ConfigEntryState.SETUP_RETRY),
        (exception.ConnectionReset(), ConfigEntryState.SETUP_RETRY),
        (exception.MissingAccountData("key"), ConfigEntryState.SETUP_ERROR),
        (ValueError("simulated unexpected error"), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_restricted_bucket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test setup entry with restricted bucket."""

    with patch(
        "b2sdk.v2.RawSimulator.get_bucket_by_name",
        side_effect=exception,
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state


async def test_periodic_issue_check(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that periodic issue check function covers all code paths."""

    captured_callback = None

    def capture_callback(hass, callback, interval):
        """Capture the callback function that gets registered."""
        nonlocal captured_callback
        captured_callback = callback
        # Return a mock that has the right interface for async_on_unload
        mock_unload = MagicMock()
        mock_unload.return_value = None
        return mock_unload

    with patch(
        "homeassistant.components.backblaze_b2.async_check_for_repair_issues",
        new_callable=AsyncMock,
    ) as mock_check_repair:
        with patch(
            "homeassistant.components.backblaze_b2.async_track_time_interval",
            side_effect=capture_callback,
        ):
            await setup_integration(hass, mock_config_entry)

        # Verify we captured the callback
        assert captured_callback is not None

        # Call the captured callback to test the periodic check functionality
        await captured_callback(datetime.now())

        # Verify that the repair check was called twice:
        # once during setup and once from our callback
        assert mock_check_repair.call_count == 2
        mock_check_repair.assert_called_with(hass, mock_config_entry)
