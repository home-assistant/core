"""Test the Google Air Quality config flow."""

from collections.abc import Generator
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
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

CLIENT_ID = "1234"
CLIENT_SECRET = "5678"


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


@pytest.mark.usefixtures("current_request_with_host", "mock_api")
@pytest.mark.parametrize("fixture_name", ["air_quality_data.json"])
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    mock_setup: Mock,
) -> None:
    """Check full flow."""
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
    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("setup_integration")
async def test_add_location_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test add location subentry flow."""
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
                CONF_LATITUDE: 50,
                CONF_LONGITUDE: 10,
            }
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry_id = list(config_entry.subentries)[0]
    subentry = config_entry.subentries[subentry_id]
    assert dict(subentry.data) == {
        "latitude": 50.0,
        "longitude": 10.0,
        "region_code": "de",
    }
    assert subentry.title == "Coordinates 50.0, 10.0"


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
        (GoogleAirQualityApiError("some error"), "access_not_configured"),
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
        DOMAIN, context={"source": config_entries.SOURCE_USER}
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

    step1 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert step1["type"] is FlowResultType.ABORT


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
) -> None:
    """Show form with base error if no data is available for the location."""

    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    result = await hass.config_entries.subentries.async_init(
        (config_entry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    step2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 0,
                CONF_LONGITUDE: 0,
            }
        },
    )
    assert step2["type"] is FlowResultType.FORM
    assert step2["step_id"] == SOURCE_USER
    assert step2["errors"] == {"base": "no_data_for_location"}


@pytest.mark.usefixtures("setup_integration_and_subentry")
async def test_already_configured(
    hass: HomeAssistant,
    config_and_subentry: MockConfigEntry,
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

    step2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 48,
                CONF_LONGITUDE: 9,
            }
        },
    )
    assert step2["type"] is FlowResultType.ABORT

    result = await hass.config_entries.subentries.async_init(
        (config_and_subentry.entry_id, "location"),
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER

    step2 = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        user_input={
            CONF_LOCATION: {
                CONF_LATITUDE: 41,
                CONF_LONGITUDE: 2,
            }
        },
    )

    assert step2["type"] is FlowResultType.CREATE_ENTRY
