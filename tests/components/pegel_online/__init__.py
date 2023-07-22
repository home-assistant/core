"""Tests for Pegel Online component."""


class PegelOnlineMock:
    """Class mock of PegelOnline."""

    def __init__(
        self,
        nearby_stations=None,
        station_details=None,
        station_measurement=None,
        side_effect=None,
    ) -> None:
        """Init the mock."""
        self.nearby_stations = nearby_stations
        self.station_details = station_details
        self.station_measurement = station_measurement
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

    async def async_get_station_measurement(self, *args):
        """Mock async_get_station_measurement."""
        if self.side_effect:
            raise self.side_effect
        return self.station_measurement

    def override_side_effect(self, side_effect):
        """Override the side_effect."""
        self.side_effect = side_effect
