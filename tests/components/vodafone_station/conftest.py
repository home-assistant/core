"""Configure tests for Vodafone Station."""

from datetime import UTC, datetime

import pytest

from .const import DEVICE_DATA_QUERY, SENSOR_DATA_QUERY

from tests.common import AsyncMock, Generator, patch


@pytest.fixture
def mock_vodafone_station_router() -> Generator[AsyncMock]:
    """Mock a Vodafone Station router."""
    with (
        patch(
            "homeassistant.components.vodafone_station.coordinator.VodafoneStationSercommApi",
            autospec=True,
        ) as mock_router,
    ):
        router = mock_router.return_value
        router.get_devices_data.return_value = DEVICE_DATA_QUERY
        router.get_sensor_data.return_value = SENSOR_DATA_QUERY
        router.convert_uptime.return_value = datetime(
            2024, 11, 19, 20, 19, 0, tzinfo=UTC
        )
        router.base_url = "https://fake_host"
        yield router
