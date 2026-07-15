"""Tests for the Solyx Energy API client.

These are unit tests for the HTTP layer: we feed a fake aiohttp session to the
client and check that each method returns data on success and raises the right
exception on failure. The full integration is exercised end-to-end in the
test_init / test_config_flow / platform tests, so here we only cover the
essentials: one happy path and one representative error per method.
"""

import asyncio
import time
from typing import TYPE_CHECKING

import pytest

from homeassistant.components.solyx_energy.api import (
    SolyxEnergyApiClient,
    SolyxEnergyAuthError,
    SolyxEnergyDataError,
    SolyxEnergyTokenError,
    SolyxEnergyWriteError,
)
from homeassistant.components.solyx_energy.const import BASE_URL, REALM_ID

if TYPE_CHECKING:
    from test_util.aiohttp import AiohttpClientMocker

DEVICE_ID = "nymo-12345"
TOKEN_PAYLOAD = {"access_token": "new-token", "expires_in": 300}
ASSET_PAYLOAD = {"attributes": {"powerBoiler": {"value": 100.0}}}
ATTRIBUTE_NAME = "operatingMode"

TOKEN_URL = f"{BASE_URL}/auth/realms/{REALM_ID}/protocol/openid-connect/token"
ASSET_URL = f"{BASE_URL}/api/{REALM_ID}/asset/{DEVICE_ID}"
ATTRIBUTE_URL = (
    f"{BASE_URL}/api/{REALM_ID}/asset/{DEVICE_ID}/attribute/{ATTRIBUTE_NAME}"
)


@pytest.fixture
async def mock_session(aioclient_mock: AiohttpClientMocker):
    """An aiohttp ClientSession bound to the aioclient_mock router."""
    session = aioclient_mock.create_session(asyncio.get_running_loop())
    yield session
    await session.close()


@pytest.fixture
def client(mock_session):
    """An API client that already holds a valid (non-expired) token (token refresh is tested separately)."""
    client = SolyxEnergyApiClient(mock_session, "test-id", "test-secret")
    client._access_token = "valid-token"
    client._token_expiry = time.monotonic() + 3600
    return client


# --- Token refresh ---


async def test_token_refresh_success(
    aioclient_mock: AiohttpClientMocker, mock_session
) -> None:
    """A successful token request stores the access token from the response."""
    aioclient_mock.post(TOKEN_URL, json=TOKEN_PAYLOAD)
    client = SolyxEnergyApiClient(mock_session, "test-id", "test-secret")
    await client._async_update_access_token()
    assert client._access_token == "new-token"


async def test_token_refresh_auth_error(
    aioclient_mock: AiohttpClientMocker, mock_session
) -> None:
    """A 401 from the token endpoint means the credentials are wrong."""
    aioclient_mock.post(TOKEN_URL, status=401)
    client = SolyxEnergyApiClient(mock_session, "test-id", "test-secret")
    with pytest.raises(SolyxEnergyAuthError):
        await client._async_update_access_token()


async def test_token_refresh_token_error(
    aioclient_mock: AiohttpClientMocker, mock_session
) -> None:
    """A non-auth HTTP failure from the token endpoint raises SolyxEnergyTokenError."""
    aioclient_mock.post(TOKEN_URL, status=503)
    client = SolyxEnergyApiClient(mock_session, "test-id", "test-secret")
    with pytest.raises(SolyxEnergyTokenError):
        await client._async_update_access_token()


# --- async_get_asset_data ---


async def test_get_asset_data_success(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A successful GET returns the parsed payload and sends the bearer token."""
    aioclient_mock.get(ASSET_URL, json=ASSET_PAYLOAD)
    result = await client.async_get_asset_data(DEVICE_ID)
    assert result == ASSET_PAYLOAD
    # The Authorization header must carry the current access token.
    _, _, _, headers = aioclient_mock.mock_calls[-1]
    assert headers["Authorization"] == "Bearer valid-token"


async def test_get_asset_data_error(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A 5xx response while reading data raises SolyxEnergyDataError."""
    aioclient_mock.get(ASSET_URL, status=500)
    with pytest.raises(SolyxEnergyDataError):
        await client.async_get_asset_data(DEVICE_ID)


async def test_get_asset_data_auth_error(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A 401 while reading data raises SolyxEnergyAuthError and clears the cached token."""
    aioclient_mock.get(ASSET_URL, status=401)
    with pytest.raises(SolyxEnergyAuthError):
        await client.async_get_asset_data(DEVICE_ID)
    assert client._access_token is None


# --- async_set_asset_attribute ---


async def test_set_asset_attribute_success(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A successful PUT sends the value as JSON with the bearer token."""
    aioclient_mock.put(ATTRIBUTE_URL)
    await client.async_set_asset_attribute(DEVICE_ID, ATTRIBUTE_NAME, "DIRECT")
    _, _, data, headers = aioclient_mock.mock_calls[-1]
    assert headers["Authorization"] == "Bearer valid-token"
    assert data == "DIRECT"


async def test_set_asset_attribute_error(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A 5xx response while writing raises SolyxEnergyWriteError."""
    aioclient_mock.put(ATTRIBUTE_URL, status=500)
    with pytest.raises(SolyxEnergyWriteError):
        await client.async_set_asset_attribute(DEVICE_ID, ATTRIBUTE_NAME, "DIRECT")


async def test_set_asset_attribute_auth_error(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """A 403 while writing raises SolyxEnergyAuthError and clears the cached token."""
    aioclient_mock.put(ATTRIBUTE_URL, status=403)
    with pytest.raises(SolyxEnergyAuthError):
        await client.async_set_asset_attribute(DEVICE_ID, ATTRIBUTE_NAME, "DIRECT")
    assert client._access_token is None


# --- async_test_connection ---


async def test_test_connection_success(
    aioclient_mock: AiohttpClientMocker, client: SolyxEnergyApiClient
) -> None:
    """async_test_connection validates credentials by fetching asset data without raising."""
    aioclient_mock.get(ASSET_URL, json=ASSET_PAYLOAD)
    await client.async_test_connection(DEVICE_ID)
