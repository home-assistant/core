"""Copyright 2024 Home Assistant Community Contributors.

Test configuration for Rejseplanen component.
"""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import zoneinfo

from py_rejseplan.api.departures import DeparturesAPIClient
from py_rejseplan.dataclasses.departure import DepartureType
from py_rejseplan.enums import TransportClass
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_ROUTE,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def make_mock_departures(stop_id: int) -> list[DepartureType]:
    """Create mock departures for a specific stop."""
    # Use a fixed base time for deterministic test data
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    if stop_id == 123456:
        # Example: 2 departures for "Work"
        departures = []
        for i, name in enumerate(["C", "E"]):
            mock_departure = MagicMock(spec=DepartureType)
            mock_departure.name = name
            mock_departure.type = TransportClass.BUS
            mock_departure.cls_id = 1
            mock_departure.direction = "End Point St."
            mock_departure.stop = "Test Stop"
            mock_departure.time = (
                (base_time + timedelta(minutes=5 + i))
                .time()
                .replace(second=0, microsecond=0)
            )
            mock_departure.date = base_time.date()
            mock_departure.track = f"{i + 1}A"
            mock_departure.final_stop = "End Station"
            mock_departure.messages = ["On time"]
            mock_departure.rtTime = (
                (base_time + timedelta(minutes=7 + i))
                .time()
                .replace(second=0, microsecond=0)
            )
            mock_departure.rtDate = base_time.date()
            mock_departure.stopExtId = 123456
            departures.append(mock_departure)
        return departures
    if stop_id == 456789:
        # Example: 1 departure for "Gym"
        mock_departure = MagicMock(spec=DepartureType)
        mock_departure.name = "A"
        mock_departure.type = TransportClass.BUS
        mock_departure.cls_id = 1
        mock_departure.direction = "North"
        mock_departure.stop = "Gym Stop"
        mock_departure.time = (
            (base_time + timedelta(minutes=10)).time().replace(second=0, microsecond=0)
        )
        mock_departure.date = base_time.date()
        mock_departure.track = "2B"
        mock_departure.final_stop = "North Station"
        mock_departure.messages = ["Delayed"]
        mock_departure.rtTime = (
            (base_time + timedelta(minutes=12)).time().replace(second=0, microsecond=0)
        )
        mock_departure.rtDate = base_time.date()
        mock_departure.stopExtId = 456789
        return [mock_departure]
    # No departures for other stops
    return []


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.rejseplanen.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Fixture for config subentries."""
    return [
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "123456",
                CONF_NAME: "Work",
                CONF_ROUTE: [],
                CONF_DIRECTION: [],
                CONF_DEPARTURE_TYPE: [],
            },
            subentry_type="stop",
            title="Work",
            subentry_id="work-subentry-id",
            unique_id=None,
        ),
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "456789",
                CONF_NAME: "Gym",
                CONF_ROUTE: [],
                CONF_DIRECTION: ["North"],
                CONF_DEPARTURE_TYPE: [],
            },
            subentry_type="stop",
            title="Gym",
            subentry_id="gym-subentry-id",
            unique_id=None,
        ),
        ConfigSubentryDataWithId(
            data={
                CONF_STOP_ID: "123789",
                CONF_NAME: "Home Location",
                CONF_ROUTE: [],
                CONF_DIRECTION: [],
                CONF_DEPARTURE_TYPE: [TransportClass.IC, TransportClass.BUS],
            },
            subentry_type="location",
            title="Home",
            subentry_id="home-subentry-id",
            unique_id=None,
        ),
    ]


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_subentries: list[ConfigSubentryDataWithId]
) -> MockConfigEntry:
    """Fixture for a config entry with subentries."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_API_KEY: "test-api-key"},
        entry_id="123456789",
        subentries_data=[*mock_subentries],
    )


@pytest.fixture(name="mock_api")
def mock_rejseplanen_coordinator(hass: HomeAssistant) -> Generator[Mock]:
    """Fixture to mock Rejseplanen API client."""
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient",
        spec=DeparturesAPIClient,
    ) as mock_api_class:
        mock_api = mock_api_class.return_value

        def get_filtered_departures(stop_id, *args, **kwargs):
            return make_mock_departures(int(stop_id))

        mock_api.get_filtered_departures = Mock(side_effect=get_filtered_departures)
        yield mock_api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: Mock,
) -> AsyncGenerator[Any, Any]:
    """Fixture to set up the integration."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.rejseplanen.coordinator.DeparturesAPIClient",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture
def patch_sensor_now():
    """Patch datetime.now() in the sensor module to return a fixed datetime."""
    fixed_now = datetime(
        2024, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
    )
    # Patch datetime in the sensor module, but preserve all classmethods except now
    with patch(
        "homeassistant.components.rejseplanen.sensor.datetime", wraps=datetime
    ) as mock_dt:
        mock_dt.now.return_value = fixed_now
        yield
