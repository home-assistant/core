"""Tests for Pegel Online component."""


class PegelOnlineMock:
    """Class mock of PegelOnline."""

    def __init__(
        self,
        nearby_stations=None,
        station_details=None,
        station_measurements=None,
        side_effect=None,
    ) -> None:
        """Init the mock."""
        self.nearby_stations = nearby_stations
        self.station_details = station_details
        self.station_measurements = station_measurements
        self.side_effect = side_effect

    async def async_get_nearby_stations(self, *args):
        """Mock async_get_nearby_stations."""
        if self.side_effect:
            raise self.side_effect
        return self.nearby_stations

    async def async_get_station_details(self, *args):
        """Mock async_get_station_details."""
        if self.side_effect:
            raise self.side_effect
        return self.station_details

    async def async_get_station_measurements(self, *args):
        """Mock async_get_station_measurements."""
        if self.side_effect:
            raise self.side_effect
        return self.station_measurements

    def override_side_effect(self, side_effect):
        """Override the side_effect."""
        self.side_effect = side_effect
