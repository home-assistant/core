"""Test Volvo coordinator."""

from unittest.mock import AsyncMock

import pytest
from volvocarsapi.api import VolvoCarsApi
from volvocarsapi.models import VolvoApiException, VolvoAuthException

from homeassistant.components.volvo.coordinator import VolvoDataCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_setup_coordinator_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test auth failure during coordinator setup."""

    api: VolvoCarsApi = mock_api.return_value
    api.async_get_vehicle_details = AsyncMock(side_effect=VolvoAuthException())

    coordinator = VolvoDataCoordinator(hass, mock_config_entry, api)

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_setup()


async def test_setup_coordinator_no_vehicle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test no vehicle during coordinator setup."""

    api: VolvoCarsApi = mock_api.return_value
    api.async_get_vehicle_details = AsyncMock(return_value=None)

    coordinator = VolvoDataCoordinator(hass, mock_config_entry, api)

    with pytest.raises(HomeAssistantError):
        await coordinator._async_setup()


async def test_update_coordinator_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test auth failure during coordinator update."""

    api: VolvoCarsApi = mock_api.return_value
    api.async_get_diagnostics = AsyncMock(side_effect=VolvoAuthException())

    coordinator = VolvoDataCoordinator(hass, mock_config_entry, api)
    await coordinator._async_setup()

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_update_coordinator_single_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: AsyncMock,
) -> None:
    """Test API returns error for single call during coordinator update."""

    api: VolvoCarsApi = mock_api.return_value
    api.async_get_diagnostics = AsyncMock(side_effect=VolvoApiException())

    coordinator = VolvoDataCoordinator(hass, mock_config_entry, api)
    await coordinator._async_setup()
    assert await coordinator._async_update_data()


async def test_update_coordinator_all_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_failure: AsyncMock,
) -> None:
    """Test API returning error for all calls during coordinator update."""

    coordinator = VolvoDataCoordinator(
        hass, mock_config_entry, mock_api_failure.return_value
    )
    await coordinator._async_setup()

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
