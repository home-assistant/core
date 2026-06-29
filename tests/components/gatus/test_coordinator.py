"""Tests for the Gatus DataUpdateCoordinator."""

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


@pytest.fixture
def mock_session() -> MagicMock:
    """Fixture to mock the aiohttp client session."""
    session = MagicMock()
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value=[{"key": "endpoint_1", "is_up": True}])
    session.get.return_value.__aenter__.return_value = response
    return session


async def test_coordinator_successful_update(hass: HomeAssistant, mock_session) -> None:
    """Test a pristine successful data refresh cycle and URL sanitization."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local/"})
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.gatus.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coordinator = GatusDataUpdateCoordinator(
            hass, config_entry, "http://gatus.local/"
        )

    assert coordinator.url == "http://gatus.local"

    data = await coordinator._async_update_data()

    assert isinstance(data, list)
    assert data[0]["key"] == "endpoint_1"
    mock_session.get.assert_called_once_with(
        "http://gatus.local/api/v1/endpoints/statuses"
    )


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (404, "Gatus API returned status code 404"),
        (500, "Gatus API returned status code 500"),
    ],
)
async def test_coordinator_http_error_status(
    hass: HomeAssistant, mock_session, status_code: int, expected_error: str
) -> None:
    """Test that non-200 HTTP response codes raise UpdateFailed errors cleanly."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local"})
    config_entry.add_to_hass(hass)

    mock_session.get.return_value.__aenter__.return_value.status = status_code

    with patch(
        "homeassistant.components.gatus.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coordinator = GatusDataUpdateCoordinator(
            hass, config_entry, "http://gatus.local"
        )

    with pytest.raises(UpdateFailed, match=expected_error):
        await coordinator._async_update_data()


async def test_coordinator_malformed_json_format(
    hass: HomeAssistant, mock_session
) -> None:
    """Test that a non-array response dictionary raises an explicit array format error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local"})
    config_entry.add_to_hass(hass)

    mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(
        return_value={"status": "error", "message": "unauthorized"}
    )

    with patch(
        "homeassistant.components.gatus.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coordinator = GatusDataUpdateCoordinator(
            hass, config_entry, "http://gatus.local"
        )

    with pytest.raises(
        UpdateFailed, match="Gatus API response was not in the expected array format"
    ):
        await coordinator._async_update_data()


async def test_coordinator_client_connection_error(
    hass: HomeAssistant, mock_session
) -> None:
    """Test that an aiohttp connection drop or client error maps to UpdateFailed."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local"})
    config_entry.add_to_hass(hass)

    mock_session.get.side_effect = aiohttp.ClientError(
        "Connection dropped by remote server"
    )

    with patch(
        "homeassistant.components.gatus.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coordinator = GatusDataUpdateCoordinator(
            hass, config_entry, "http://gatus.local"
        )

    with pytest.raises(UpdateFailed, match="Error communicating with Gatus API:"):
        await coordinator._async_update_data()


async def test_coordinator_upstream_timeout_error(
    hass: HomeAssistant, mock_session
) -> None:
    """Test that a physical read timeout maps cleanly into an active translation layer exception."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local"})
    config_entry.add_to_hass(hass)

    mock_session.get.side_effect = TimeoutError("Request timed out after 10s")

    with patch(
        "homeassistant.components.gatus.coordinator.async_get_clientsession",
        return_value=mock_session,
    ):
        coordinator = GatusDataUpdateCoordinator(
            hass, config_entry, "http://gatus.local"
        )

    with pytest.raises(UpdateFailed, match="Error communicating with Gatus API:"):
        await coordinator._async_update_data()
