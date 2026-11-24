"""Test the Microsoft Text-to-Speech setup."""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests.exceptions import ConnectionError as RequestsConnectionError

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import http_error


@pytest.mark.usefixtures("mock_tts_translator")
async def test_setup_and_unload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting up and unloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "state", "translation_key"),
    [
        pytest.param(
            http_error(HTTPStatus.UNAUTHORIZED),
            ConfigEntryState.SETUP_ERROR,
            "invalid_api_key",
            id="invalid_api_key",
        ),
        pytest.param(
            http_error(HTTPStatus.INTERNAL_SERVER_ERROR),
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            id="http_error",
        ),
        pytest.param(
            RequestsConnectionError,
            ConfigEntryState.SETUP_RETRY,
            "cannot_connect",
            id="cannot_connect",
        ),
    ],
)
async def test_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tts_translator: MagicMock,
    side_effect: Exception,
    state: ConfigEntryState,
    translation_key: str,
) -> None:
    """Test the setup fails if the credentials can't be validated."""
    mock_tts_translator.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == translation_key
