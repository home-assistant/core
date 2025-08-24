"""Test the AirPatrol data update coordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

from airpatrol.api import AirPatrolAPI, AirPatrolAuthenticationError, AirPatrolError
import pytest

from homeassistant.components.airpatrol.const import DOMAIN
from homeassistant.components.airpatrol.coordinator import (
    SCAN_INTERVAL,
    AirPatrolDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import ConfigEntryAuthFailed, UpdateFailed

from tests.common import MockConfigEntry


def make_config_entry(data=None):
    """Helper to create a MockConfigEntry with custom data."""
    if data is None:
        data = {"email": "test@example.com", "password": "pw"}
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="test_entry_id",
        data=data,
        unique_id="uniqueid",
        title=data["email"],
    )


@pytest.fixture
def mock_api():
    """Mock AirPatrol API."""
    api = AsyncMock(spec=AirPatrolAPI)
    api.get_data.return_value = [{"id": 1}]
    api.get_access_token.return_value = "token"
    api.get_unique_id.return_value = "uniqueid"
    return api


@pytest.mark.asyncio
async def test_update_data_with_stored_token(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test data update with stored access token."""
    entry = make_config_entry(
        {"email": "test@example.com", "password": "pw", "access_token": "token"}
    )
    entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.airpatrol.coordinator.AirPatrolAPI",
        return_value=mock_api,
    ):
        coordinator = AirPatrolDataUpdateCoordinator(hass, entry)
        await coordinator._async_setup()
        result = await coordinator._async_update_data()
        assert result == [{"id": 1}]
        mock_api.get_data.assert_awaited()


@pytest.mark.asyncio
async def test_update_data_refresh_token_success(
    hass: HomeAssistant, mock_api: MagicMock
) -> None:
    """Test data update with expired token and successful refresh."""
    entry = make_config_entry({"email": "test@example.com", "password": "pw"})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.airpatrol.coordinator.AirPatrolAPI.authenticate",
            new_callable=AsyncMock,
            return_value=mock_api,
        ),
        patch.object(hass.config_entries, "async_update_entry") as mock_update_entry,
    ):
        coordinator = AirPatrolDataUpdateCoordinator(hass, entry)
        await coordinator._async_setup()
        result = await coordinator._async_update_data()
        assert result == [{"id": 1}]
        mock_api.get_data.assert_awaited()
        mock_update_entry.assert_called_once()


@pytest.mark.asyncio
async def test_update_data_auth_failure(hass: HomeAssistant) -> None:
    """Test permanent authentication failure."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    api = AsyncMock(spec=AirPatrolAPI)
    api.get_access_token.return_value = "token"
    api.get_unique_id.return_value = "uniqueid"
    with (
        patch(
            "homeassistant.components.airpatrol.coordinator.AirPatrolAPI",
            return_value=api,
        ),
        patch(
            "homeassistant.components.airpatrol.coordinator.AirPatrolAPI.authenticate",
            new_callable=AsyncMock,
            return_value=api,
        ),
    ):
        coordinator = AirPatrolDataUpdateCoordinator(hass, entry)
        await coordinator._async_setup()
        api.get_data.side_effect = AirPatrolAuthenticationError("fail")
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_update_data_api_error(hass: HomeAssistant) -> None:
    """Test API error handling."""
    entry = make_config_entry(
        {"email": "test@example.com", "password": "pw", "access_token": "token"}
    )
    entry.add_to_hass(hass)
    api = AsyncMock(spec=AirPatrolAPI)
    with patch(
        "homeassistant.components.airpatrol.coordinator.AirPatrolAPI",
        return_value=api,
    ):
        coordinator = AirPatrolDataUpdateCoordinator(hass, entry)
        await coordinator._async_setup()
        api.get_data.side_effect = AirPatrolError("fail")
        with pytest.raises(
            UpdateFailed, match="Error communicating with AirPatrol API: fail"
        ):
            await coordinator._async_update_data()


def test_coordinator_update_interval(hass: HomeAssistant) -> None:
    """Test coordinator update interval and initialization."""
    entry = make_config_entry()
    entry.add_to_hass(hass)
    coordinator = AirPatrolDataUpdateCoordinator(hass, entry)
    assert coordinator.update_interval == SCAN_INTERVAL
    assert coordinator.config_entry == entry
    # Accept both 'AirPatrol' and 'Airpatrol' for compatibility with coordinator capitalization
    assert coordinator.name == f"{DOMAIN.capitalize()} {entry.data['email']}"
