"""Test the Google Air Quality config flow."""

from collections.abc import Generator
import datetime
from typing import Any
from unittest.mock import Mock, patch

from google_air_quality_api.exceptions import (
    GoogleAirQualityApiError,
    NoDataForLocationError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.google_air_quality.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import CONFIG_ENTRY_ID, FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"
NEW_USER_ID = "new-user-id"


@pytest.fixture(name="mock_setup")
def mock_setup_entry() -> Generator[Mock]:
    """Fixture to mock out integration setup."""
    with patch(
        "homeassistant.components.google_air_quality.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="updated_token_entry", autouse=True)
def mock_updated_token_entry() -> dict[str, Any]:
    """Fixture to provide any test specific overrides to token data from the oauth token endpoint."""
    return {}


@pytest.fixture(name="mock_oauth_token_request", autouse=True)
def mock_token_request(
    aioclient_mock: AiohttpClientMocker,
    token_entry: dict[str, any],
    updated_token_entry: dict[str, Any],
) -> None:
    """Fixture to provide a fake response from the oauth token endpoint."""
    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            **token_entry,
            **updated_token_entry,
        },
    )


@pytest.mark.freeze_time(datetime.datetime(2025, 6, 12, tzinfo=datetime.UTC))
@pytest.mark.usefixtures("current_request_with_host", "mock_api")
@pytest.mark.parametrize("fixture_name", ["air_quality_data.json"])
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup: Mock,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=https://www.googleapis.com/auth/cloud-platform"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "auth_implementation": DOMAIN,
        "token": {
            "access_token": FAKE_ACCESS_TOKEN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "scope": [
                "https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/userinfo.profile",
            ],
            "type": "Bearer",
            "expires_at": 1749690000.0,
            "expires_in": 3600,
        },
    }
    assert result["title"] == "Test Name"
    assert result["context"]["unique_id"] == CONFIG_ENTRY_ID


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


@pytest.mark.usefixtures(
    "current_request_with_host",
    "setup_credentials",
    "mock_api",
)
@pytest.mark.parametrize(
    ("api_error_user_info", "reason"),
    [
        (GoogleAirQualityApiError("some error"), "access_not_configured"),
        (Exception("some error"), "unknown"),
    ],
)
async def test_oauth_fail(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_client_no_auth: ClientSessionGenerator,
    reason: str,
    mock_api: Mock,
) -> None:
    """Check flow aborts if api is not enabled."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        "&scope=https://www.googleapis.com/auth/cloud-platform"
        "+https://www.googleapis.com/auth/userinfo.profile"
        "&access_type=offline&prompt=consent"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures(
    "current_request_with_host",
    "setup_credentials",
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
    await hass.async_block_till_done()
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
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures(
    "current_request_with_host",
)
@pytest.mark.parametrize("updated_token_entry", [{"scope": "nada"}])
async def test_missing_scope(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup: Mock,
) -> None:
    """Check if the scopes are there, before prestenting the map."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("setup_integration")
@pytest.mark.usefixtures("current_request_with_host", "mock_api")
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


@pytest.mark.usefixtures("current_request_with_host")
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
