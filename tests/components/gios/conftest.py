"""Fixtures for GIOS integration tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

from gios.model import GiosSensors, GiosStation, Sensor as GiosSensor
import pytest

from homeassistant.components.gios.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

STATIONS = [
    {
        "Identyfikator stacji": 123,
        "Nazwa stacji": "Test Name 1",
        "WGS84 φ N": "99.99",
        "WGS84 λ E": "88.88",
    },
    {
        "Identyfikator stacji": 321,
        "Nazwa stacji": "Test Name 2",
        "WGS84 φ N": "77.77",
        "WGS84 λ E": "66.66",
    },
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123",
        data={"station_id": 123, "name": "Home"},
        entry_id="86129426118ae32020417a53712d6eef",
    )


GIOS_SENSORS = GiosSensors(
    aqi=GiosSensor(name="AQI", id=None, index=None, value="good"),
    c6h6=GiosSensor(name="benzene", id=658, index="very_good", value=0.23789),
    co=GiosSensor(name="carbon monoxide", id=660, index="good", value=251.874),
    no=GiosSensor(name="nitrogen monoxide", id=664, index=None, value=5.1),
    no2=GiosSensor(name="nitrogen dioxide", id=665, index="good", value=7.13411),
    nox=GiosSensor(name="nitrogen oxides", id=666, index=None, value=5.5),
    o3=GiosSensor(name="ozone", id=667, index="good", value=95.7768),
    pm10=GiosSensor(
        name="particulate matter 10", id=14395, index="good", value=16.8344
    ),
    pm25=GiosSensor(name="particulate matter 2.5", id=670, index="good", value=4),
    so2=GiosSensor(name="sulfur dioxide", id=672, index="very_good", value=4.35478),
)

GIOS_STATIONS = {
    123: GiosStation(id=123, name="Test Name 1", latitude=99.99, longitude=88.88),
    321: GiosStation(id=321, name="Test Name 2", latitude=77.77, longitude=66.66),
}


@pytest.fixture
async def mock_gios(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Return a mocked GIOS client."""
    with (
        patch("homeassistant.components.gios.Gios") as mock_gios,
        patch("homeassistant.components.gios.coordinator.Gios", mock_gios),
        patch("homeassistant.components.gios.config_flow.Gios", mock_gios),
    ):
        mock_gios.return_value.create = AsyncMock(return_value=mock_gios)
        mock_gios.create = AsyncMock(return_value=mock_gios)

        mock_gios.create.return_value.async_update = AsyncMock(
            return_value=GIOS_SENSORS
        )
        mock_gios.measurement_stations = GIOS_STATIONS
        mock_gios.station_id = 123
        mock_gios.station_name = GIOS_STATIONS[mock_gios.station_id].name

        yield mock_gios


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gios: MagicMock,
) -> MockConfigEntry:
    """Set up the GIOS integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
