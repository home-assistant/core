"""Test the Google Air Quality config flow."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from google_air_quality_api.exceptions import (
    GoogleAirQualityApiError,
    NoDataForLocationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.google_air_quality.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import CONFIG_ENTRY_ID

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

NEW_USER_ID = "new-user-id"


@pytest.fixture(name="mock_setup")
def mock_setup_entry() -> Generator[Mock]:
    """Fixture to mock out integration setup."""
    with patch(
        "homeassistant.components.google_air_quality.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.mark.usefixtures("current_request_with_host")
@pytest.mark.parametrize(
    ("api_error", "reason", "type"),
    [
        (
            GoogleAirQualityApiError("some error"),
            "unable_to_fetch",
            FlowResultType.ABORT,
        ),
        (
            Exception("some error"),
            "unknown",
            FlowResultType.ABORT,
        ),
    ],
)
async def test_full_flow(
    hass: HomeAssistant,
    reason: str,
    type: FlowResultType,
    mock_api: Mock,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.google_air_quality.config_flow.GoogleAirQualityApi.async_air_quality",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: CONFIG_ENTRY_ID,
            },
        )
        await hass.async_block_till_done()

    assert result["reason"] == reason
    assert result["type"] is type
    mock_api.async_air_quality.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.google_air_quality.config_flow.GoogleAirQualityApi.async_air_quality",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: CONFIG_ENTRY_ID,
            },
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "API-Key: *********234"
    assert result["data"] == {}


@pytest.mark.parametrize(
    ("api_error_reverse_geocode", "title", "name"),
    [
        (
            None,
            "Straße Ohne Straßennamen, 88637 Buchheim, Deutschland",
            "Straße Ohne Straßennamen",
        ),
        (GoogleAirQualityApiError("some error"), "Coordinates 50.0, 10.0", "50.0_10.0"),
    ],
)
@pytest.mark.usefixtures("setup_integration")
async def test_add_location_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_api: Mock,
    api_error_reverse_geocode: Exception | None,
    title: str,
    name: str,
) -> None:
    """Test add location subentry flow."""
    assert config_entry.state is ConfigEntryState.LOADED
    mock_api.async_reverse_geocode.side_effect = api_error_reverse_geocode
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 50,
                CONF_LONGITUDE: 10,
            }
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LATITUDE: 50.0,
        CONF_LONGITUDE: 10.0,
        CONF_NAME: name,
    }
    assert result["unique_id"] == "50.0_10.0"
    assert result["title"] == title


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures(
    "mock_api",
)
@pytest.mark.parametrize(
    ("api_error", "reason"),
    [
        (GoogleAirQualityApiError("some error"), "unable_to_fetch"),
        (Exception("some error"), "unknown"),
    ],
)
async def test_api_not_enabled(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    reason: str,
) -> None:
    """Check flow aborts if api is not enabled."""
    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 0,
                CONF_LONGITUDE: 0,
            }
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.parametrize(
    ("fixture_name", "api_error"),
    [("air_quality_data.json", NoDataForLocationError())],
)
async def test_no_data_for_location_shows_form(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup: Mock,
    mock_api: Mock,
) -> None:
    """Show form with base error if no data is available for the location."""
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 0,
                CONF_LONGITUDE: 0,
            }
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "no_data_for_location"}

    mock_api.async_air_quality.side_effect = None
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 40.7128,
                CONF_LONGITUDE: 134.0060,
            }
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_LATITUDE: 40.7128,
        CONF_LONGITUDE: 134.0060,
        CONF_NAME: "Straße Ohne Straßennamen",
    }
    assert result["unique_id"] == "40.7128_134.006"


@pytest.mark.parametrize("fixture_name", ["air_quality_data.json"])
@pytest.mark.usefixtures("setup_integration_and_subentry")
async def test_already_configured(
    hass: HomeAssistant,
    config_and_subentry: MockConfigEntry,
    config_entry_2: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    mock_api: Mock,
) -> None:
    """Snapshot test of the sensors."""
    await hass.async_block_till_done()
    assert config_and_subentry.state is ConfigEntryState.LOADED
    result = await hass.config_entries.subentries.async_init(
        (config_and_subentry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 48,
                CONF_LONGITUDE: 9,
            }
        },
    )
    assert result["type"] is FlowResultType.ABORT

    result = await hass.config_entries.subentries.async_init(
        (config_and_subentry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 41,
                CONF_LONGITUDE: 2,
            }
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    # Test adding a new main entry with the same coordinates

    config_entry_2.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (config_entry_2.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 41,
                CONF_LONGITUDE: 2,
            }
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
