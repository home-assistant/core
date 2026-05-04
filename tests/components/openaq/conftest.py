"""Common fixtures for the OpenAQ tests."""

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.openaq.const import CONF_LOCATION_ID, DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY

from tests.common import MockConfigEntry

API_KEY = "test-api-key"
LOCATION_ID = 2178
LOCATION_NAME = "Del Norte"
SUBENTRY_ID = "ABCDEF"


def make_response(results: list[object]) -> SimpleNamespace:
    """Return an OpenAQ SDK response."""
    return SimpleNamespace(results=results)


def make_location(
    location_id: int = LOCATION_ID, name: str = LOCATION_NAME
) -> SimpleNamespace:
    """Return an OpenAQ location."""
    return SimpleNamespace(id=location_id, name=name, locality="Albuquerque")


def make_parameter(name: str, units: str = "µg/m³") -> SimpleNamespace:
    """Return an OpenAQ parameter."""
    return SimpleNamespace(name=name, units=units)


def make_sensor(
    sensor_id: int, parameter: str, units: str = "µg/m³", value: float | None = None
) -> SimpleNamespace:
    """Return an OpenAQ sensor."""
    latest = None if value is None else SimpleNamespace(value=value)
    return SimpleNamespace(
        id=sensor_id,
        parameter=make_parameter(parameter, units),
        latest=latest,
    )


def make_latest(sensor_id: int, value: float | None) -> SimpleNamespace:
    """Return an OpenAQ latest measurement."""
    return SimpleNamespace(sensors_id=sensor_id, value=value)


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.openaq.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return an OpenAQ config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OpenAQ",
        data={CONF_API_KEY: API_KEY},
        subentries_data=[
            ConfigSubentryData(
                data={CONF_LOCATION_ID: LOCATION_ID},
                subentry_id=SUBENTRY_ID,
                subentry_type="location",
                title=LOCATION_NAME,
                unique_id=str(LOCATION_ID),
            )
        ],
    )


@pytest.fixture
def mock_openaq_client() -> Generator[AsyncMock]:
    """Mock the OpenAQ client."""
    with (
        patch("homeassistant.components.openaq.AsyncOpenAQ") as mock_init,
        patch(
            "homeassistant.components.openaq.config_flow.AsyncOpenAQ",
            new=mock_init,
        ),
    ):
        client = mock_init.return_value
        client.close = AsyncMock()
        client.parameters = SimpleNamespace()
        client.locations = SimpleNamespace()
        client.parameters.list = AsyncMock()
        client.locations.get = AsyncMock()
        client.locations.list = AsyncMock()
        client.locations.latest = AsyncMock()
        client.locations.sensors = AsyncMock()
        client.parameters.list.return_value = make_response([])
        client.locations.get.return_value = make_response([make_location()])
        client.locations.list.return_value = make_response([make_location()])
        client.locations.latest.return_value = make_response(
            [
                make_latest(1, 8.5),
                make_latest(2, 12.1),
                make_latest(3, 33.2),
                make_latest(4, 0.4),
                make_latest(5, 415),
                make_latest(6, 15),
                make_latest(7, 22),
                make_latest(8, 4),
                make_latest(9, 6),
                make_latest(10, 17),
                make_latest(11, 0.9),
                make_latest(12, 123),
            ]
        )
        client.locations.sensors.return_value = make_response(
            [
                make_sensor(1, "pm1"),
                make_sensor(2, "pm25"),
                make_sensor(3, "pm10"),
                make_sensor(4, "co", "ppm"),
                make_sensor(5, "co2", "ppm"),
                make_sensor(6, "no2", "ppb"),
                make_sensor(7, "o3", "ppb"),
                make_sensor(8, "so2", "ppb"),
                make_sensor(9, "no", "ppb"),
                make_sensor(10, "nox", "ppb"),
                make_sensor(11, "bc"),
                make_sensor(12, "unsupported"),
            ]
        )
        yield client
