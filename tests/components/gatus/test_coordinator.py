"""Tests for the Gatus DataUpdateCoordinator."""

from unittest.mock import AsyncMock, patch

# Import your library's exceptions to simulate failures
from gatus_api.client import GatusClientError
import pytest

from homeassistant.components.gatus.const import DOMAIN
from homeassistant.components.gatus.coordinator import GatusDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_coordinator_successful_update(hass: HomeAssistant) -> None:
    """Test a pristine successful data refresh cycle and URL sanitization."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local/"})
    config_entry.add_to_hass(hass)

    coordinator = GatusDataUpdateCoordinator(hass, config_entry, "http://gatus.local/")

    assert coordinator.url == "http://gatus.local"

    # Mock the third-party library method directly
    mock_data = [{"key": "endpoint_1", "is_up": True}]
    with patch.object(
        coordinator.client, "get_endpoints_statuses", AsyncMock(return_value=mock_data)
    ) as mock_get:
        data = await coordinator._async_update_data()
        mock_get.assert_called_once()

    assert isinstance(data, list)
    assert data[0]["key"] == "endpoint_1"


async def test_coordinator_client_error(hass: HomeAssistant) -> None:
    """Test that a library exception wraps cleanly into UpdateFailed."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={"url": "http://gatus.local"})
    config_entry.add_to_hass(hass)

    coordinator = GatusDataUpdateCoordinator(hass, config_entry, "http://gatus.local")

    with (
        patch.object(
            coordinator.client,
            "get_endpoints_statuses",
            AsyncMock(
                side_effect=GatusClientError(
                    "Error communicating with Gatus API: status code 500"
                )
            ),
        ),
        pytest.raises(UpdateFailed, match="Error communicating with Gatus API:"),
    ):
        await coordinator._async_update_data()
