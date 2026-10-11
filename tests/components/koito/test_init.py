"""Test failures before platforms are forwarded."""

from unittest.mock import AsyncMock

from aiokoito import KoitoAuthenticationError, KoitoConnectionError, KoitoResponseError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


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
