"""Mocks for the Ituran integration."""

from datetime import datetime

from pyituran import Ituran
import pytest


class MockVehicle:
    """Mock vehicle."""

    def __init__(self, index: int) -> None:
        """Initialize mock vehicle."""
        self.__license_plate = "1234567" + str(index)

    @property
    def license_plate(self) -> str:
        """Mock license plate."""
        return self.__license_plate

    @property
    def make(self) -> str:
        """Mock make."""
        return "mock make"

    @property
    def model(self) -> str:
        """Mock make."""
        return "mock model"

    @property
    def mileage(self) -> int:
        """Mock mileage."""
        return 1000

    @property
    def speed(self) -> int:
        """Mock speed."""
        return 20

    @property
    def gps_coordinates(self) -> tuple[float, float]:
        """Mock GPS coordinates."""
        return (25.0, -71.0)

    @property
    def address(self) -> str:
        """Mock address."""
        return "Bermuda Triangle"

    @property
    def heading(self) -> int:
        """Mock heading."""
        return 150

    @property
    def last_update(self) -> datetime:
        """Mock last update time."""
        return datetime.now()


@pytest.fixture
def ituran_fixture(number_of_vehicles: int, monkeypatch: pytest.MonkeyPatch):
    """Fixture for Ituran.get_vehicles() function."""

    async def mock_get_vehicles(_):
        return [MockVehicle(index) for index in range(number_of_vehicles)]

    monkeypatch.setattr(Ituran, "get_vehicles", mock_get_vehicles)
