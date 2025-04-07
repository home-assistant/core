"""Mocks for the Ituran integration."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, PropertyMock, patch
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.ituran.const import (
    CONF_ID_OR_PASSPORT,
    CONF_MOBILE_ID,
    CONF_PHONE_NUMBER,
    DOMAIN,
)

from .const import MOCK_CONFIG_DATA

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ituran.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=f"Ituran {MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT]}",
        domain=DOMAIN,
        data={
            CONF_ID_OR_PASSPORT: MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
            CONF_PHONE_NUMBER: MOCK_CONFIG_DATA[CONF_PHONE_NUMBER],
            CONF_MOBILE_ID: MOCK_CONFIG_DATA[CONF_MOBILE_ID],
        },
        unique_id=MOCK_CONFIG_DATA[CONF_ID_OR_PASSPORT],
    )


class MockVehicle:
    """Mock vehicle."""

    def __init__(self) -> None:
        """Initialize mock vehicle."""
        self.license_plate = "12345678"
        self.make = "mock make"
        self.model = "mock model"
        self.mileage = 1000
        self.speed = 20
        self.gps_coordinates = (25.0, -71.0)
        self.address = "Bermuda Triangle"
        self.heading = 150
        self.last_update = datetime(
            2024, 1, 1, 0, 0, 0, tzinfo=ZoneInfo("Asia/Jerusalem")
        )
        self.battery_voltage = 12.0


@pytest.fixture
def mock_ituran() -> Generator[AsyncMock]:
    """Return a mocked PalazzettiClient."""
    with (
        patch(
            "homeassistant.components.ituran.coordinator.Ituran",
            autospec=True,
        ) as ituran,
        patch(
            "homeassistant.components.ituran.config_flow.Ituran",
            new=ituran,
        ),
    ):
        mock_ituran = ituran.return_value
        mock_ituran.is_authenticated.return_value = False
        mock_ituran.authenticate.return_value = True
        mock_ituran.get_vehicles.return_value = [MockVehicle()]
        type(mock_ituran).mobile_id = PropertyMock(
            return_value=MOCK_CONFIG_DATA[CONF_MOBILE_ID]
        )

        yield mock_ituran
