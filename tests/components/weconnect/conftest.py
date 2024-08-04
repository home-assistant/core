"""Mocks for the WeConnect library."""

from weconnect.addressable import AddressableDict
from weconnect.elements.vehicle import Vehicle

MOCK_VIN = "VW1234567890123456"


def mock_weconnect_login(self) -> None:
    """Mock the login method."""


def mock_weconnect_update(self) -> None:
    """Mock the update method."""


def mock_weconnect_vehicles(self) -> AddressableDict[str, Vehicle]:
    """Mock the vehicles property."""
    vehicles = AddressableDict(localAddress="vehicles", parent=self)
    vehicles[MOCK_VIN] = Vehicle(
        weConnect=self,
        vin=MOCK_VIN,
        parent=self.__vehicles,
        fromDict={
            "vin": MOCK_VIN,
            "model": "ID.4",
            "enrollmentStatus": "",
            "userRoleStatus": "",
            "devicePlatform": "",
            "brandCode": "V",
            "nickname": "car",
        },
        updateCapabilities=False,
        updatePictures=False,
    )

    return vehicles
