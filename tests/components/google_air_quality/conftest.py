"""Test fixtures for Google Air Quality."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from google_air_quality_api.model import AirQualityData
import pytest

from homeassistant.components.google_air_quality.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

USER_IDENTIFIER = "user-identifier-1"
CONFIG_ENTRY_ID = "api-key-1234"
CONFIG_ENTRY_ID_2 = "user-identifier-2"
CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
FAKE_ACCESS_TOKEN = "some-access-token"
FAKE_REFRESH_TOKEN = "some-refresh-token"
EXPIRES_IN = 3600


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.google_air_quality.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Fixture for a config and a subentry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={"api_key": "test-api-key", "referrer": None},
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={
                    "latitude": 10.1,
                    "longitude": 20.1,
                },
                subentry_type="location",
                title="Home",
                subentry_id="home-subentry-id",
                unique_id=None,
            )
        ],
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture(name="fixture_name")
def mock_fixture_name() -> str | None:
    """Provide a json fixture file to load air quality data."""
    return None


@pytest.fixture(name="api_error")
def mock_api_error() -> Exception | None:
    """Provide a json fixture file to load air quality data."""
    return None


@pytest.fixture(name="mock_api")
def mock_client_api(
    fixture_name: str,
    api_error: Exception,
) -> Generator[Mock]:
    """Set up fake Google Air Quality API responses from fixtures."""
    responses = load_json_object_fixture("air_quality_data.json", DOMAIN)
    with (
        patch(
            "homeassistant.components.google_air_quality.GoogleAirQualityApi",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.google_air_quality.config_flow.GoogleAirQualityApi",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.async_air_quality.return_value = AirQualityData.from_dict(responses)

        yield api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
) -> AsyncGenerator[Any, Any]:
    """Fixture to set up the integration."""
    config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google_air_quality.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="setup_integration_and_subentry")
async def mock_setup_integration_and_subentry(
    hass: HomeAssistant,
    config_and_subentry: MockConfigEntry,
    mock_api: Mock,
) -> AsyncGenerator[Any, Any]:
    """Fixture to set up the integration with a subentry."""
    config_and_subentry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google_air_quality.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(config_and_subentry.entry_id)
        await hass.async_block_till_done()
        yield
