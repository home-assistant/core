"""Test missing time series key returns empty dict."""

import logging

import pytest

from homeassistant.components.fitbit.api import FitbitApi
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_async_get_latest_time_series_missing_key(
    hass: HomeAssistant,
) -> None:
    """Test FitbitApi gracefully handles missing 'foods-log-water' key."""

    class MockFitbitApi(FitbitApi):
        def __init__(self, hass: HomeAssistant) -> None:
            super().__init__(hass, None)
            # Manually set _logger so real HA setup isn't required
            self._logger = logging.getLogger(__name__)

        async def async_get_access_token(self) -> dict[str, str | int]:
            return {
                "access_token": "abc",
                "refresh_token": "xyz",
                "expires_at": 1234567890,
            }

        async def _async_get_client(self):
            class MockClient:
                system = None

                def time_series(self, resource_type: str, period: str) -> dict:
                    # Simulate Fitbit API missing the expected key
                    return {}

            return MockClient()

        async def async_get_unit_system(self) -> str:
            return "METRIC"

    async def mock_run(func) -> dict:
        return func()

    api = MockFitbitApi(hass)
    api._run = mock_run

    result = await api.async_get_latest_time_series("foods/log/water")
    assert result == {}
