"""Test configuration for Rejseplanen component."""

from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import zoneinfo

from py_rejseplan.api.departures import DeparturesAPIClient
from py_rejseplan.dataclasses.departure import Departure
from py_rejseplan.dataclasses.product_type import ProductType
from py_rejseplan.enums import TransportClass
import pytest

from homeassistant.components.rejseplanen.const import (
    CONF_API_KEY,
    CONF_DEPARTURE_TYPE,
    CONF_DIRECTION,
    CONF_NAME,
    CONF_STOP_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def make_mock_departures(stop_id: int) -> list[Departure]:
    """Create mock departures for a specific stop."""
    # Use a fixed base time for deterministic test data
    base_time = datetime(2024, 1, 1, 12, 0, 0)
    departures = []
    if stop_id == 123456:
        # Example: 2 departures for "Work"
        for i, (name, line) in enumerate([("Bus 207", "207"), ("Bus 216", "216")]):
            mock_departure = MagicMock(spec=Departure)
            mock_departure.name = name
            mock_departure.line = line
            mock_departure.direction = "End Point St."
            mock_departure.stop = "Test Stop"
            mock_departure.time = (
                (base_time + timedelta(minutes=5 + i))
                .time()
                .replace(second=0, microsecond=0)
            )
            mock_departure.date = base_time.date()
            mock_departure.track = f"{i + 1}A"
            mock_departure.rtTrack = f"{i + 1}A"
            mock_departure.final_stop = "End Station"
            mock_departure.messages = ["On time"]
            mock_departure.rtTime = (
                (base_time + timedelta(minutes=7 + i))
                .time()
                .replace(second=0, microsecond=0)
            )
            mock_departure.rtDate = base_time.date()
            mock_departure.stopExtId = 123456

            mock_product = MagicMock(spec=ProductType)
            mock_product.cls_id = TransportClass.BUS.value
            mock_product.line = name
            mock_product.operator = "Test Operator"
            mock_product.name = name
            mock_departure.product = mock_product

            departures.append(mock_departure)
        return departures
    if stop_id == 456789:
        # Past departure

        past_product = MagicMock(spec=ProductType)
        past_product.cls_id = TransportClass.BUS.value

        past_dep = MagicMock(spec=Departure)
        past_dep.name = "A"
        past_dep.type = TransportClass.BUS
        past_dep.product = past_product
        past_dep.direction = "South"
        past_dep.stop = "Gym Stop"
        past_dep.time = (
            (base_time - timedelta(minutes=10)).time().replace(second=0, microsecond=0)
        )
        past_dep.date = base_time.date()
        past_dep.track = "2B"
        past_dep.final_stop = "North Station"
        past_dep.messages = ["Delayed"]
        past_dep.rtTime = (
            (base_time - timedelta(minutes=8)).time().replace(second=0, microsecond=0)
        )
        past_dep.rtDate = base_time.date()
        past_dep.stopExtId = 456789
        departures.append(past_dep)

        # Buffer departure (just inside buffer)
        buffer_dep = MagicMock(spec=Departure)
        buffer_dep.name = "A"
        buffer_dep.type = TransportClass.TOG

        buffer_product = MagicMock(spec=ProductType)
        buffer_product.cls_id = TransportClass.TOG.value
        buffer_dep.product = buffer_product

        buffer_dep.direction = "North"
        buffer_dep.stop = "Gym Stop"
        buffer_dep.time = (
            (base_time - timedelta(minutes=1)).time().replace(second=0, microsecond=0)
        )
        buffer_dep.date = base_time.date()
        buffer_dep.track = "2B"
        buffer_dep.final_stop = "North Station"
        buffer_dep.messages = ["Delayed"]
        buffer_dep.rtTime = (
            (base_time - timedelta(seconds=30)).time().replace(second=0, microsecond=0)
        )
        buffer_dep.rtDate = base_time.date()
        buffer_dep.stopExtId = 456789
        departures.append(buffer_dep)

        # Future departure
        future_dep = MagicMock(spec=Departure)
        future_dep.name = "A"
        future_dep.type = TransportClass.ICL

        future_product = MagicMock(spec=ProductType)
        future_product.cls_id = TransportClass.ICL.value
        future_dep.product = future_product

        future_dep.direction = "North"
        future_dep.stop = "Gym Stop"
        future_dep.time = (
            (base_time + timedelta(minutes=10)).time().replace(second=0, microsecond=0)
        )
        future_dep.date = base_time.date()
        future_dep.track = "2B"
        future_dep.final_stop = "North Station"
        future_dep.messages = ["Delayed"]
        future_dep.rtTime = (
            (base_time + timedelta(minutes=12)).time().replace(second=0, microsecond=0)
        )
        future_dep.rtDate = base_time.date()
        future_dep.stopExtId = 456789
        departures.append(future_dep)

        return departures
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
                CONF_STOP_ID: 123456,
                CONF_NAME: "Work",
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
                CONF_STOP_ID: 456789,
                CONF_NAME: "Gym",
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
                CONF_STOP_ID: 123789,
                CONF_NAME: "Home Location",
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

        def get_departures(stop_ids, *args, **kwargs):
            all_departures = []
            for stop_id in stop_ids:
                all_departures.extend(make_mock_departures(int(stop_id)))
            mock_board = MagicMock()
            mock_board.departures = all_departures
            return (mock_board, None)

        mock_api.get_departures = Mock(side_effect=get_departures)
        mock_api.calculate_departure_type_bitflag = Mock(return_value=0)
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
    """Patch datetime.now() and dt_util.now() in the sensor module to return a fixed datetime."""
    fixed_now = datetime(
        2024, 1, 1, 12, 0, 0, tzinfo=zoneinfo.ZoneInfo("Europe/Copenhagen")
    )
    # Patch both datetime.now and dt_util.now in the sensor module
    with (
        patch(
            "homeassistant.components.rejseplanen.sensor.datetime", wraps=datetime
        ) as mock_dt,
        patch(
            "homeassistant.components.rejseplanen.sensor.dt_util.now",
            return_value=fixed_now,
        ),
    ):
        mock_dt.now.return_value = fixed_now
        yield
