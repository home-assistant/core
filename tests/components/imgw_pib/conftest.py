"""Common fixtures for the IMGW-PIB tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from imgw_pib import HydrologicalData, SensorData
import pytest

from homeassistant.components.imgw_pib.const import DOMAIN

from tests.common import MockConfigEntry

HYDROLOGICAL_DATA = HydrologicalData(
    station="Station Name",
    river="River Name",
    station_id="123",
    water_level=SensorData(name="Water Level", value=526.0),
    flood_alarm_level=SensorData(name="Flood Alarm Level", value=630.0),
    flood_warning_level=SensorData(name="Flood Warning Level", value=590.0),
    water_temperature=SensorData(name="Water Temperature", value=10.8),
    flood_alarm=False,
    flood_warning=False,
    water_level_measurement_date=datetime(2024, 4, 27, 10, 0, tzinfo=UTC),
    water_temperature_measurement_date=datetime(2024, 4, 27, 10, 10, tzinfo=UTC),
)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.imgw_pib.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_imgw_pib_client() -> Generator[AsyncMock, None, None]:
    """Mock a ImgwPib client."""
    with (
        patch(
            "homeassistant.components.imgw_pib.ImgwPib", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.imgw_pib.config_flow.ImgwPib",
            new=mock_client,
        ),
    ):
        client = mock_client.create.return_value
        client.get_hydrological_data.return_value = HYDROLOGICAL_DATA
        client.hydrological_stations = {"123": "River Name (Station Name)"}

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="River Name (Station Name)",
        unique_id="123",
        data={
            "station_id": "123",
        },
    )
