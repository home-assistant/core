"""Tests for the Nanoleaf integration init."""

from unittest.mock import AsyncMock

from aionanoleaf2 import InvalidToken, Unavailable
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_without_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device does not support events."""
    mock_nanoleaf.supports_events = False
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_not_called()


async def test_setup_entry_with_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device supports events."""
    mock_nanoleaf.supports_events = True
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_called_once()


@pytest.mark.parametrize(
    ("exception", "state", "translation_key"),
    [
        pytest.param(
            Unavailable,
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            id="unavailable",
        ),
        pytest.param(
            InvalidToken,
            ConfigEntryState.SETUP_ERROR,
            "invalid_token",
            id="invalid_token",
        ),
    ],
)
async def test_setup_entry_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    exception: type[Exception],
    state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test setup fails when the first refresh raises an error."""
    mock_nanoleaf.get_info.side_effect = exception
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == translation_key
