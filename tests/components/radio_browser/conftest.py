"""Fixtures for the Radio Browser integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.radio_browser.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="My Radios",
        domain=DOMAIN,
        data={},
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.radio_browser.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Radio Browser integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_countries():
    "Generate mock countries for the countries method of the radios object."

    class MockCountry:
        """Country Object for Radios."""

        def __init__(self, code, name) -> None:
            """Initialize a mock country."""
            self.code = code
            self.name = name
            self.favicon = "fake.png"

    return [MockCountry("US", "United States")]


@pytest.fixture
def mock_stations():
    "Generate mock stations for the stations method of the radios object."

    class MockStation:
        """Station object for Radios."""

        def __init__(self, country_code, latitude, longitude, name, uuid) -> None:
            """Initialize a mock station."""
            self.country_code = country_code
            self.latitude = latitude
            self.longitude = longitude
            self.uuid = uuid
            self.name = name
            self.codec = "MP3"
            self.favicon = "fake.png"

    return [
        MockStation(
            country_code="US",
            latitude=45.52000,
            longitude=-122.63961,
            name="Near Station 1",
            uuid="1",
        ),
        MockStation(
            country_code="US",
            latitude=None,
            longitude=None,
            name="Unknown location station",
            uuid="2",
        ),
        MockStation(
            country_code="US",
            latitude=47.57071,
            longitude=-122.21148,
            name="Moderate Far Station",
            uuid="3",
        ),
        MockStation(
            country_code="US",
            latitude=45.73943,
            longitude=-121.51859,
            name="Near Station 2",
            uuid="4",
        ),
        MockStation(
            country_code="US",
            latitude=44.99026,
            longitude=-69.27804,
            name="Really Far Station",
            uuid="5",
        ),
    ]


@pytest.fixture
def mock_radios(mock_countries, mock_stations):
    """Provide a radios mock object."""
    radios = MagicMock()
    radios.countries = AsyncMock(return_value=mock_countries)
    radios.stations = AsyncMock(return_value=mock_stations)
    return radios


@pytest.fixture
def patch_radios(monkeypatch: pytest.MonkeyPatch, mock_radios):
    """Replace the radios object in the source with the mock object (with mock stations and countries)."""

    def _patch(source):
        monkeypatch.setattr(type(source), "radios", mock_radios)

    return _patch
