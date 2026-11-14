"""Common fixtures for the GeoSphere Austria Forecast tests."""

from collections.abc import Generator
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture
from zamg import NwpForecast, NwpForecastRecord

from homeassistant.components.geosphere_austria_forecast.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def frozen_time(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the time between two forecast records."""
    freezer.move_to("2026-09-26T05:10:00+00:00")


@pytest.fixture
def request_slot_seconds() -> float:
    """Return how long a request keeps its slot; no wait unless a test asks."""
    return 0


@pytest.fixture(autouse=True)
def request_slot_hold(request_slot_seconds: float) -> Generator[None]:
    """Hold a request slot as long as the test asks for."""
    with patch(
        "homeassistant.components.geosphere_austria_forecast.coordinator.SECONDS_PER_REQUEST_SLOT",
        request_slot_seconds,
    ):
        yield


@pytest.fixture
def forecast() -> NwpForecast:
    """Return the forecast from the fixture file."""
    data = load_json_object_fixture("forecast.json", DOMAIN)
    return NwpForecast(
        reference_time=datetime.fromisoformat(data["reference_time"]),
        requested_latitude=data["requested_latitude"],
        requested_longitude=data["requested_longitude"],
        resolved_latitude=data["resolved_latitude"],
        resolved_longitude=data["resolved_longitude"],
        records=tuple(
            NwpForecastRecord(
                **{
                    **record,
                    "valid_time": datetime.fromisoformat(record["valid_time"]),
                }
            )
            for record in data["records"]
        ),
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.geosphere_austria_forecast.async_setup_entry",
        return_value=None,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_nwp_client(forecast: NwpForecast) -> Generator[MagicMock]:
    """Mock the GeoSphere Austria NWP client."""
    with (
        patch(
            "homeassistant.components.geosphere_austria_forecast.NwpClient",
            autospec=True,
        ) as client_cls,
        patch(
            "homeassistant.components.geosphere_austria_forecast.config_flow.NwpClient",
            new=client_cls,
        ),
    ):
        client = client_cls.return_value
        client.get_forecast = AsyncMock(return_value=forecast)
        yield client


@pytest.fixture
def six_locations(hass: HomeAssistant) -> list[MockConfigEntry]:
    """Add config entries for six locations, one more than the request limit."""
    entries = [
        MockConfigEntry(
            domain=DOMAIN,
            title=f"Location {index}",
            data={CONF_LATITUDE: 47.0 + index / 10, CONF_LONGITUDE: 15.0},
            unique_id=f"location-{index}",
        )
        for index in range(6)
    ]
    for entry in entries:
        entry.add_to_hass(hass)
    return entries


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for one location."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Pixendorf",
        entry_id="01JZ4Q1GE0SPHERE0000000000",
        data={CONF_LATITUDE: 48.2877, CONF_LONGITUDE: 15.98486},
        unique_id="48.2850-15.9802",
    )
