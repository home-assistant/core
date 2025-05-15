"""Test the Google Photos config flow."""

from collections.abc import Generator
from typing import Any
from unittest.mock import Mock, patch

from google_air_quality_api.exceptions import GooglePhotosApiError
import pytest

from homeassistant import config_entries
from homeassistant.components.google_air_quality.const import (
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
)
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow

from .conftest import EXPIRES_IN, FAKE_ACCESS_TOKEN, FAKE_REFRESH_TOKEN

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


@pytest.fixture(autouse=True)
def mock_patch_api(mock_api: Mock) -> Generator[None]:
    """Fixture to patch the config flow api."""
    with patch(
        "homeassistant.components.google_air_quality.config_flow.GoogleAirQualityApi",
        return_value=mock_api,
    ):
        yield


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
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "coordinates"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 50,
                CONF_LONGITUDE: 10,
            }
        },
    )
    config_entry = result["result"]
    assert config_entry.unique_id == "50.0_10.0"
    assert config_entry.title == "Coordinates 50.0, 10.0"
    config_entry_data = dict(config_entry.data)
    assert "token" in config_entry_data
    assert "expires_at" in config_entry_data["token"]
    del config_entry_data["token"]["expires_at"]
    assert config_entry_data == {
        "auth_implementation": DOMAIN,
        "latitude": 50.0,
        "longitude": 10.0,
        "region_code": "de",
        "token": {
            "access_token": FAKE_ACCESS_TOKEN,
            "expires_in": EXPIRES_IN,
            "refresh_token": FAKE_REFRESH_TOKEN,
            "type": "Bearer",
            "scope": (
                "https://www.googleapis.com/auth/cloud-platform"
                " https://www.googleapis.com/auth/userinfo.profile"
            ),
        },
    }
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup.mock_calls) == 1


@pytest.mark.usefixtures(
    "current_request_with_host",
    "setup_credentials",
    "mock_api",
)
@pytest.mark.parametrize(
    "api_error",
    [
        GooglePhotosApiError("some error"),
    ],
)
async def test_api_not_enabled(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "coordinates"

    coords = {
        CONF_LOCATION: {
            CONF_LATITUDE: hass.config.latitude,
            CONF_LONGITUDE: hass.config.longitude,
        }
    }
    result = await hass.config_entries.flow.async_configure(result["flow_id"], coords)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "access_not_configured"
    assert result["description_placeholders"]["message"].endswith("some error")

    # @pytest.mark.usefixtures("current_request_with_host", "setup_credentials")
    # async def test_general_exception(
    #     hass: HomeAssistant,
    #     hass_client_no_auth: ClientSessionGenerator,
    #     mock_api: Mock,
    # ) -> None:
    #     """Check flow aborts if exception happens."""
    #     result = await hass.config_entries.flow.async_init(
    #         DOMAIN, context={"source": config_entries.SOURCE_USER}
    #     )
    #     state = config_entry_oauth2_flow._encode_jwt(
    #         hass,
    #         {
    #             "flow_id": result["flow_id"],
    #             "redirect_uri": "https://example.com/auth/external/callback",
    #         },
    #     )
    #     assert result["url"] == (
    #         f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
    #         "&redirect_uri=https://example.com/auth/external/callback"
    #         f"&state={state}"
    #         "&scope=https://www.googleapis.com/auth/cloud-platform"
    #         "+https://www.googleapis.com/auth/userinfo.profile"
    #         "&access_type=offline&prompt=consent"
    #     )

    #     client = await hass_client_no_auth()
    #     resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    #     assert resp.status == 200
    #     assert resp.headers["content-type"] == "text/html; charset=utf-8"

    #     mock_api.async_air_quality.side_effect = Exception

    #     result = await hass.config_entries.flow.async_configure(result["flow_id"])

    #     assert result["type"] is FlowResultType.ABORT
    # assert result["reason"] == "unknown"
