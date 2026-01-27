"""Test fixtures for Google Air Quality."""

from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from google_air_quality_api.model import AirQualityCurrentConditionsData
import pytest

from homeassistant.components.google_air_quality import CONF_REFERRER
from homeassistant.components.google_air_quality.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
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
def mock_subentries() -> list[ConfigSubentryDataWithId]:
    """Fixture for subentries."""
    return [
        ConfigSubentryDataWithId(
            data={
                CONF_LATITUDE: 10.1,
                CONF_LONGITUDE: 20.1,
            },
            subentry_type="location",
            title="Home",
            subentry_id="home-subentry-id",
            unique_id=None,
        )
    ]


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_subentries: list[ConfigSubentryDataWithId]
) -> MockConfigEntry:
    """Fixture for a config and a subentry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        data={CONF_API_KEY: "test-api-key", CONF_REFERRER: None},
        entry_id="123456789",
        subentries_data=[*mock_subentries],
    )


@pytest.fixture(name="mock_api")
def mock_client_api() -> Generator[Mock]:
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
        api.async_get_current_conditions.return_value = (
            AirQualityCurrentConditionsData.from_dict(responses)
        )

        yield api


@pytest.fixture(name="setup_integration")
async def mock_setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api: Mock,
) -> AsyncGenerator[Any, Any]:
    """Fixture to set up the integration."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.google_air_quality.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        yield
