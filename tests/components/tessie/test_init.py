"""Test the Tessie init."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientError
import pytest
from tesla_fleet_api.exceptions import (
    InvalidRequest,
    InvalidToken,
    ServiceUnavailable,
    TeslaFleetError,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .common import setup_platform


async def test_load_unload(hass: HomeAssistant) -> None:
    """Test load and unload."""

    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_auth_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with an authentication error."""

    mock_get_state_of_all_vehicles.side_effect = InvalidToken()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR


async def test_unknown_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with a non-retryable fleet API error."""

    mock_get_state_of_all_vehicles.side_effect = InvalidRequest()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.reason == "Failed to connect"


async def test_retryable_api_failure(
    hass: HomeAssistant, mock_get_state_of_all_vehicles: AsyncMock
) -> None:
    """Test init with a retryable fleet API error."""

    mock_get_state_of_all_vehicles.side_effect = ServiceUnavailable()
    entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_products_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on products."""

    with patch(
        "homeassistant.components.tessie.Tessie.products", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_scopes_error(hass: HomeAssistant) -> None:
    """Test init with a fleet error on scopes."""

    with patch(
        "homeassistant.components.tessie.Tessie.scopes", side_effect=TeslaFleetError
    ):
        entry = await setup_platform(hass)
        assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("patch_target", "exception"),
    [
        pytest.param(
            None,
            ClientConnectionError(),
            id="list_vehicles-connection_error",
        ),
        pytest.param(
            None,
            ClientError(),
            id="list_vehicles-client_error",
        ),
        pytest.param(
            "homeassistant.components.tessie.Tessie.scopes",
            ClientConnectionError(),
            id="scopes-connection_error",
        ),
        pytest.param(
            "homeassistant.components.tessie.Tessie.scopes",
            ClientError(),
            id="scopes-client_error",
        ),
        pytest.param(
            "homeassistant.components.tessie.Tessie.products",
            ClientConnectionError(),
            id="products-connection_error",
        ),
        pytest.param(
            "homeassistant.components.tessie.Tessie.products",
            ClientError(),
            id="products-client_error",
        ),
    ],
)
async def test_aiohttp_client_error_retries(
    hass: HomeAssistant,
    mock_get_state_of_all_vehicles: AsyncMock,
    patch_target: str | None,
    exception: ClientError,
) -> None:
    """Test that aiohttp.ClientError on any setup call triggers SETUP_RETRY.

    Covers list_vehicles(), scopes(), and products() — all network calls that
    tesla_fleet_api does not wrap in TeslaFleetError.
    """
    if patch_target is None:
        mock_get_state_of_all_vehicles.side_effect = exception
        entry = await setup_platform(hass)
    else:
        with patch(patch_target, side_effect=exception):
            entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(ClientConnectionError(), id="connection_error"),
        pytest.param(ClientError(), id="client_error"),
    ],
)
async def test_aiohttp_client_error_on_live_status_retries(
    hass: HomeAssistant,
    exception: ClientError,
) -> None:
    """Test that aiohttp.ClientError during live_status() triggers SETUP_RETRY."""
    with patch(
        "tesla_fleet_api.tessie.EnergySite.live_status",
        side_effect=exception,
    ):
        entry = await setup_platform(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
