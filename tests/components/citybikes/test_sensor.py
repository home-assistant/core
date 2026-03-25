"""Tests for the CityBikes sensor platform."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, Mock, patch

from citybikes import model as citybikes_model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.citybikes import sensor as citybikes_sensor
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(name="station_factory")
def station_factory_fixture() -> Callable[[dict[str, object]], citybikes_model.Station]:
    """Create CityBikes station objects."""
    return lambda extra: citybikes_model.Station(
        id="station-1",
        name="Station 1",
        free_bikes=5,
        empty_slots=8,
        latitude=40.0,
        longitude=-73.0,
        timestamp="2026-03-22T00:00:00Z",
        extra=extra,
    )


@pytest.fixture(name="mock_citybikes_client")
def mock_citybikes_client_fixture() -> Generator[Mock]:
    """Mock the CityBikes client."""
    with patch.object(citybikes_sensor, "CitybikesClient") as mock_client:
        mock_client.return_value.close = AsyncMock()
        yield mock_client.return_value


async def _async_setup_citybikes_sensor(
    hass: HomeAssistant,
    mock_citybikes_client: Mock,
    station: citybikes_model.Station,
) -> None:
    """Set up the CityBikes sensor platform."""
    network = citybikes_model.Network.from_dict(
        {
            "id": "mock-network",
            "name": "Mock Network",
            "location": {
                "latitude": 40.0,
                "longitude": -73.0,
                "city": "Test City",
                "country": "US",
            },
            "href": "/v2/networks/mock-network",
            "stations": [station.__dict__],
        }
    )
    mock_citybikes_client.network.return_value.fetch = AsyncMock(return_value=network)

    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "citybikes",
                    "network": "mock-network",
                    "stations": ["station-1"],
                }
            ]
        },
    )
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("extra", "snapshot_name"),
    [
        pytest.param(
            {citybikes_sensor.ATTR_UID: "uid-1", "ebikes": 2},
            "with_ebikes",
            id="with_ebikes",
        ),
        pytest.param(
            {citybikes_sensor.ATTR_UID: "uid-1"},
            "without_ebikes",
            id="without_ebikes",
        ),
    ],
)
async def test_sensor_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_citybikes_client: Mock,
    station_factory: Callable[[dict[str, object]], citybikes_model.Station],
    extra: dict[str, object],
    snapshot_name: str,
) -> None:
    """Test CityBikes sensor state snapshots."""
    await _async_setup_citybikes_sensor(
        hass, mock_citybikes_client, station_factory(extra)
    )

    assert (state := hass.states.get("sensor.mock_network_station_1"))
    assert state == snapshot(name=snapshot_name)
