"""Tests for the weheat initialization."""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from weheat.abstractions.discovery import HeatPumpDiscovery

from homeassistant.components.weheat import UnauthorizedException
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

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
    ("setup_exception", "expected_setup_state"),
    [
        (HTTPStatus.BAD_REQUEST, ConfigEntryState.SETUP_ERROR),
        (HTTPStatus.UNAUTHORIZED, ConfigEntryState.SETUP_ERROR),
        (HTTPStatus.FORBIDDEN, ConfigEntryState.SETUP_ERROR),
        (HTTPStatus.GATEWAY_TIMEOUT, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_fail(
    hass: HomeAssistant,
    mock_weheat_discover: AsyncMock,
    mock_weheat_heat_pump: AsyncMock,
    mock_heat_pump_info: HeatPumpDiscovery.HeatPumpInfo,
    mock_config_entry: MockConfigEntry,
    setup_exception: Exception,
    expected_setup_state: ConfigEntryState,
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

    assert mock_config_entry.state is expected_setup_state


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


@pytest.mark.usefixtures("setup_credentials")
async def test_oauth_implementation_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unavailable OAuth implementation raises ConfigEntryNotReady."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.weheat.async_get_config_entry_implementation",
        side_effect=ImplementationUnavailableError,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
