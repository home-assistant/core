"""Tests for the MAWAQIT integration setup."""

from unittest.mock import MagicMock

import httpx
from mawaqit import APIConnectionError, MawaqitError
from mawaqit.types import PrayerTimes
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MOSQUE_UUID

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_mawaqit_client")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the config entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_fetches_the_mosque(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
) -> None:
    """Test the prayer times of the configured mosque are fetched."""
    await setup_integration(hass, mock_config_entry)
    mock_mawaqit_client.mosques.prayer_times.assert_awaited_once_with(MOSQUE_UUID)


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(
            APIConnectionError(httpx.Request("GET", "https://mawaqit.net/api")),
            id="connection",
        ),
        pytest.param(MawaqitError(), id="mawaqit_error"),
    ],
)
async def test_setup_retry_on_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    error: MawaqitError,
) -> None:
    """Test setup is retried when the prayer times cannot be fetched."""
    mock_mawaqit_client.mosques.prayer_times.side_effect = error
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_retry_on_unknown_timezone(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mawaqit_client: MagicMock,
    prayer_times: PrayerTimes,
) -> None:
    """Test setup is retried when the time zone of the mosque is unknown."""
    mock_mawaqit_client.mosques.prayer_times.return_value = prayer_times.model_copy(
        update={"timezone": "Not/AZone"}
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
