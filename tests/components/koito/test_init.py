"""Test failures before platforms are forwarded."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aiokoito import KoitoAuthenticationError, KoitoConnectionError, KoitoResponseError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    ("error", "state"),
    [
        (KoitoConnectionError(), ConfigEntryState.SETUP_RETRY),
        (KoitoResponseError(), ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_failure(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
    state: ConfigEntryState,
) -> None:
    """Reject/defer initial setup without creating misleading available entities."""
    mock_client.async_fetch_data.side_effect = error
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is state
    assert hass.states.get("sensor.koito_plays") is None


async def test_setup_authentication_failure(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A rejected key starts reauthentication before entities are registered."""
    mock_client.async_fetch_data.side_effect = KoitoAuthenticationError()
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert hass.states.get("sensor.koito_plays") is None
    assert hass.config_entries.flow.async_progress()[0]["context"]["source"] == "reauth"


@pytest.mark.parametrize(
    ("failure", "message", "retry_after"),
    [
        (
            KoitoConnectionError("Unable to connect to Koito"),
            "Unable to connect to Koito",
            None,
        ),
        (
            KoitoResponseError("Koito returned invalid JSON"),
            "Koito returned invalid JSON",
            None,
        ),
        (
            KoitoConnectionError(
                "Koito request failed (HTTP 429)", status=429, retry_after=120
            ),
            "Koito request failed (HTTP 429)",
            120,
        ),
    ],
)
async def test_refresh_failure_preserves_client_context(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    failure: Exception,
    message: str,
    retry_after: int | None,
) -> None:
    """Retain actionable error context without repeating outage logs."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    coordinator = mock_config_entry.runtime_data
    mock_client.async_fetch_data.side_effect = failure
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    error = coordinator.last_exception
    assert isinstance(error, UpdateFailed)
    assert str(error) == f"Unable to refresh Koito data: {message}"
    assert error.__cause__ is failure
    assert error.retry_after == retry_after
    assert hass.states.get("sensor.koito_plays").state == "unavailable"
    freezer.tick(timedelta(seconds=121))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert caplog.messages.count(f"Error fetching Koito data: {error}") == 1
    mock_client.async_fetch_data.side_effect = None
    freezer.tick(timedelta(seconds=121))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("sensor.koito_plays").state == "42"
    assert caplog.messages.count("Fetching Koito data recovered") == 1
