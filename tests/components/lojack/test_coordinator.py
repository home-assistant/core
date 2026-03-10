"""Tests for the LoJack coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import MockApiError, MockAuthenticationError
from .const import TEST_DEVICE_ID

from tests.common import MockConfigEntry


async def test_coordinator_fetch_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lojack_client: AsyncMock,
) -> None:
    """Test coordinator fetches data successfully."""
    await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data
    assert len(coordinators) == 1
    coordinator = coordinators[0]
    assert coordinator.data is not None
    assert coordinator.data.device_id == TEST_DEVICE_ID


async def test_coordinator_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    mock_device.get_location = AsyncMock(
        side_effect=MockAuthenticationError("Token expired")
    )

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.AuthenticationError",
            MockAuthenticationError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_coordinator_api_error_raises_update_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test coordinator raises UpdateFailed on API error."""
    mock_device.get_location = AsyncMock(
        side_effect=MockApiError("API error")
    )

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.coordinator.ApiError",
            MockApiError,
        ),
    ):
        mock_config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_coordinator_no_location(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test coordinator handles None location from API gracefully."""
    mock_device.get_location = AsyncMock(return_value=None)

    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[mock_device])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    coordinators = mock_config_entry.runtime_data
    assert len(coordinators) == 1
    vehicle = coordinators[0].data
    assert vehicle.device_id == TEST_DEVICE_ID
    assert vehicle.latitude is None
    assert vehicle.longitude is None
    assert vehicle.accuracy is None


async def test_coordinator_no_vehicles(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles account with no vehicles."""
    client = AsyncMock()
    client.user_id = "user123"
    client.list_devices = AsyncMock(return_value=[])
    client.close = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "homeassistant.components.lojack.LoJackClient.create",
            return_value=client,
        ),
        patch(
            "homeassistant.components.lojack.config_flow.LoJackClient.create",
            return_value=client,
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data == []
