"""Unit tests for iottycloud API."""

from unittest.mock import patch

from aiohttp import ClientSession
import pytest

from homeassistant.components.iotty import api
from homeassistant.components.iotty.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_api_create_fail(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test API creation with no session."""

    with pytest.raises(ValueError, match="websession"):
        api.IottyProxy(hass, None, None)

    with pytest.raises(ValueError, match="oauth_session"):
        api.IottyProxy(hass, aioclient_mock, None)


async def test_api_create_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aiohttp_client_session: None,
    local_oauth_impl: ClientSession,
) -> None:
    """Test API creation. We're checking that we can create an IottyProxy without raising."""

    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.data["auth_implementation"] is not None

    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    api.IottyProxy(hass, aiohttp_client_session, local_oauth_impl)


@patch(
    "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.valid_token", False
)
async def test_api_getaccesstoken_tokennotvalid_reloadtoken(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    local_oauth_impl: ClientSession,
    mock_aioclient: None,
    aiohttp_client_session: ClientSession,
) -> None:
    """Test getting access token.

    If a request with an invalid token is made, a request for a new token is done,
    and the resulting token is used for future calls.
    """
    config_entry_oauth2_flow.async_register_implementation(
        hass, DOMAIN, local_oauth_impl
    )

    new_token = "ACCESS_TOKEN_1"

    mock_aioclient.post(
        "https://token.url", json={"access_token": new_token, "expires_in": 100}
    )

    mock_aioclient.post("https://example.com", status=201)

    mock_config_entry.add_to_hass(hass)
    oauth2_session = config_entry_oauth2_flow.OAuth2Session(
        hass, mock_config_entry, local_oauth_impl
    )

    iotty = api.IottyProxy(hass, aiohttp_client_session, oauth2_session)

    tok = await iotty.async_get_access_token()
    assert tok == new_token
