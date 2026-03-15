"""Tests for the Emby integration setup."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import MagicMock, patch

from homeassistant.components.emby.const import CannotConnect, InvalidAuth
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import TEST_HOST, TEST_PORT, TEST_SERVER_ID

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_emby_server: MagicMock,
) -> None:
    """Test successful config entry setup."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.emby._validate_connection",
            return_value=TEST_SERVER_ID,
        ),
        patch("homeassistant.components.emby.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that InvalidAuth during setup results in auth-failed entry state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.emby._validate_connection",
        side_effect=InvalidAuth,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_setup_entry_cannot_connect(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that CannotConnect during setup results in a retryable entry state."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.emby._validate_connection",
        side_effect=CannotConnect,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_http_non_401_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test that a non-401 HTTP error during validation results in a retryable entry state."""
    mock_config_entry.add_to_hass(hass)

    aioclient_mock.get(
        f"http://{TEST_HOST}:{TEST_PORT}/System/Info",
        status=HTTPStatus.INTERNAL_SERVER_ERROR,
    )

    with patch("homeassistant.components.emby.PLATFORMS", []):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
