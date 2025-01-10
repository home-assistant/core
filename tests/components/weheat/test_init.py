"""Tests for the Spotify initialization."""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.components.weheat import UnauthorizedException
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import ClientResponseError


@pytest.mark.usefixtures("setup_credentials")
async def test_setup(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Weheat setup."""
    mock_weheat_discover.return_value = [mock_heat_pump_info]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    "setup_exception",
    [
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
        HTTPStatus.GATEWAY_TIMEOUT,
    ],
)
async def test_setup_fail(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
    setup_exception: Exception,
) -> None:
    """Test the Weheat setup with invalid token setup."""
    with (
        patch(
            "homeassistant.components.weheat.OAuth2Session.async_ensure_token_valid",
            side_effect=ClientResponseError(
                Mock(real_url="http://example.com"), None, status=setup_exception
            ),
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    if setup_exception in (
        HTTPStatus.BAD_REQUEST,
        HTTPStatus.UNAUTHORIZED,
        HTTPStatus.FORBIDDEN,
    ):
        # If it is related to authorization, it should error
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    else:
        # Any other error suggests a retry later will fix it
        assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("setup_credentials")
async def test_setup_fail_discover(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Weheat setup with and error from the heat pump discovery."""
    mock_weheat_discover.side_effect = UnauthorizedException()

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
