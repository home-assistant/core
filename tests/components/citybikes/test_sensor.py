"""Tests for the CityBikes sensor platform."""

from collections.abc import Callable, Generator
from unittest.mock import AsyncMock, Mock, patch

from citybikes import model as citybikes_model
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.citybikes import sensor as citybikes_sensor
from homeassistant.core import HomeAssistant

from . import setup_integration


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


@pytest.mark.parametrize(
    "extra",
    [
        pytest.param(
            {citybikes_sensor.ATTR_UID: "uid-1", citybikes_sensor.EXTRA_EBIKES: 2},
            id="with_ebikes",
        ),
        pytest.param(
            {citybikes_sensor.ATTR_UID: "uid-1"},
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
) -> None:
    """Test CityBikes sensor state snapshots."""
    await setup_integration(hass, mock_citybikes_client, station_factory(extra))

    assert (state := hass.states.get("sensor.mock_network_station_1"))
    assert state == snapshot
