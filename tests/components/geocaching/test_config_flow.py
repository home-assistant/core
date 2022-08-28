"""Test the Geocaching config flow."""
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from unittest.mock import MagicMock

from aiohttp.test_utils import TestClient
import pytest

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.geocaching.const import (
    DOMAIN,
    ENVIRONMENT,
    ENVIRONMENT_URLS,
)
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from . import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker

CURRENT_ENVIRONMENT_URLS = ENVIRONMENT_URLS[ENVIRONMENT]


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: Callable[[], Awaitable[TestClient]],
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Check full flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "flow_id" in result

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    assert result.get("type") == FlowResultType.EXTERNAL_STEP
    assert result.get("step_id") == "auth"
    assert result.get("url") == (
        f"{CURRENT_ENVIRONMENT_URLS['authorize_url']}?response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}&scope=*"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_existing_entry(
    hass: HomeAssistant,
    hass_client_no_auth: Callable[[], Awaitable[TestClient]],
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
    setup_credentials: None,
) -> None:
    """Check existing entry."""
    mock_config_entry.add_to_hass(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "flow_id" in result
    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    await hass.config_entries.flow.async_configure(result["flow_id"])
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_oauth_error(
    hass: HomeAssistant,
    hass_client_no_auth: Callable[[], Awaitable[TestClient]],
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
) -> None:
    """Check if aborted when oauth error occurs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert "flow_id" in result

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": REDIRECT_URI,
        },
    )
    assert result.get("type") == FlowResultType.EXTERNAL_STEP

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK

    # No user information is returned from API
    mock_geocaching_config_flow.update.return_value.user = None

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    result2 = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result2.get("type") == FlowResultType.ABORT
    assert result2.get("reason") == "oauth_error"

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauthentication(
    hass: HomeAssistant,
    hass_client_no_auth: Callable[[], Awaitable[TestClient]],
    aioclient_mock: AiohttpClientMocker,
    current_request_with_host: None,
    mock_geocaching_config_flow: MagicMock,
    mock_setup_entry: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Geocaching reauthentication."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_REAUTH}
    )

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert "flow_id" in flows[0]

    result = await hass.config_entries.flow.async_configure(flows[0]["flow_id"], {})
    assert "flow_id" in result

    # pylint: disable=protected-access
    state = config_entry_oauth2_flow._encode_jwt(
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == HTTPStatus.OK
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        CURRENT_ENVIRONMENT_URLS["token_url"],
        json={
            "access_token": "mock-access-token",
            "token_type": "bearer",
            "expires_in": 3599,
            "refresh_token": "mock-refresh_token",
        },
    )

    await hass.config_entries.flow.async_configure(result["flow_id"])

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1
