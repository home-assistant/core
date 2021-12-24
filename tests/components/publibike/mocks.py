"""Mocks for PubliBike."""

from unittest.mock import MagicMock, Mock

from pypublibike.location import Location
from pypublibike.publibike import PubliBike
from pypublibike.station import Station


def _get_mock_bikes(count=2, ebike=True, bat_lvls=None):
    bikes = []
    for i, x in enumerate(range(count)):
        n = 1000 if ebike else 100
        bike = Mock()
        bike.name = n + x + 1
        if ebike:
            bike.batteryLevel = bat_lvls[i]
        bikes.append(bike)
    return bikes


def _get_mock_bike():
    mock_station = MagicMock(Station(123, Location(1.0, 2.0)), stationId=123)
    mock_station.name = "test_station"
    mock_station.ebikes = _get_mock_bikes(2, ebike=True, bat_lvls=[1, 100])
    mock_station.bikes = _get_mock_bikes(2, ebike=False)
    mock_pb = Mock(PubliBike())
    mock_pb.getStations = Mock(return_value=[mock_station])
    mock_pb.findNearestStationTo = Mock(return_value=mock_station)
    return mock_pb
