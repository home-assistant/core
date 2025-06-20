"""Test fixtures for Google Air Quality."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from google_air_quality_api.api import GoogleAirQualityApi
from google_air_quality_api.model import AirQualityData
from google_air_quality_api.model_reverse_geocoding import PlacesResponse
import pytest

from homeassistant.components.google_air_quality.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
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


@pytest.fixture(autouse=True)
def mock_patch_api(mock_api: Mock) -> Generator[None]:
    """Fixture to patch the config flow api."""
    with patch(
        "homeassistant.components.google_air_quality.config_flow.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        yield


@pytest.fixture(name="config_entry_id")
def mock_config_entry_id() -> str | None:
    """Provide a json fixture file to load a config entry ID."""
    return CONFIG_ENTRY_ID


@pytest.fixture(name="config_entry_id_2")
def mock_config_entry_id_2() -> str:
    """Provide second config entry ID (different)."""
    return CONFIG_ENTRY_ID_2


@pytest.fixture(name="config_entry")
def mock_config_entry(config_entry_id: str) -> MockConfigEntry:
    """Fixture for a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_id,
        title="API-Key: ********234",
    )


@pytest.fixture(name="config_entry_2")
def mock_config_entry_2(config_entry_id_2: str) -> MockConfigEntry:
    """Fixture for the second config entry (different ID)."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_id_2,
        title="API-Key: ********567",
    )


@pytest.fixture(name="config_and_subentry")
def mock_config_and_subentry(config_entry_id: str) -> MockConfigEntry:
    """Fixture for a config and a subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=config_entry_id,
        title="API-Key: ********234",
        entry_id="123456789",
        subentries_data=[
            ConfigSubentryData(
                data={
                    "latitude": 48,
                    "longitude": 9,
                    CONF_NAME: "Straße Ohne Straßennamen",
                },
                subentry_id="ABCDEF",
                subentry_type="location",
                title="Coordinates 48, 9",
                unique_id="48.0_9.0",
            )
        ],
    )


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
    mock_api = AsyncMock(GoogleAirQualityApi, autospec=True)
    responses = load_json_object_fixture("air_quality_data.json", DOMAIN)
    mock_api.async_air_quality.return_value = AirQualityData.from_dict(responses)
    mock_api.async_air_quality.side_effect = api_error
    reverse_geocode_data = load_json_object_fixture("reverse_geocoding.json", DOMAIN)
    mock_api.async_reverse_geocode.return_value = PlacesResponse.from_dict(
        reverse_geocode_data
    )
    return mock_api


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
