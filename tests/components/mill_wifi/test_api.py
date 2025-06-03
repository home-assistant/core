# tests/test_api.py
import pytest
from httpx import Response 
from pytest_httpx import HTTPXMock

from custom_components.mill_wifi.api import MillApiClient, AuthenticationError, MillApiError, USER_AGENT
from custom_components.mill_wifi.const import (
    BASE_URL,
    ENDPOINT_AUTH_SIGN_IN,
    ENDPOINT_AUTH_REFRESH,
    ENDPOINT_CUSTOMER_SETTINGS
)

@pytest.fixture # Ensure this fixture is defined as it was missing in the error for test_token_refresh
def mill_client():
    return MillApiClient(username="test@example.com", password="password")

@pytest.mark.asyncio
async def test_successful_login(mill_client: MillApiClient, httpx_mock: HTTPXMock):
    # ... (ensure match_headers here also uses "user-agent" if it's an issue)
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_AUTH_SIGN_IN}",
        method="POST",
        json={"idToken": "fake_id_token", "refreshToken": "fake_refresh_token"},
        status_code=200,
        match_headers={"user-agent": USER_AGENT} # Ensure lowercase
    )
    await mill_client.async_setup() 
    await mill_client.login()
    assert mill_client.access_token == "fake_id_token"
    # ...


@pytest.mark.asyncio
async def test_login_failure(mill_client: MillApiClient, httpx_mock: HTTPXMock):
    # ... (ensure match_headers here also uses "user-agent" if applicable)
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_AUTH_SIGN_IN}",
        method="POST",
        json={"error": "Invalid credentials"},
        status_code=401,
        match_headers={"user-agent": USER_AGENT} # Ensure lowercase
    )
    await mill_client.async_setup()
    with pytest.raises(MillApiError): 
        await mill_client.login()
    # ...


@pytest.mark.asyncio
async def test_token_refresh(mill_client: MillApiClient, httpx_mock: HTTPXMock):
    """Test token refresh mechanism (which involves a full re-login on force_refresh=True)."""
    # 1. Initial login
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_AUTH_SIGN_IN}",
        method="POST",
        json={"idToken": "old_id_token", "refreshToken": "old_refresh_token"},
        status_code=200,
        match_headers={"user-agent": USER_AGENT} # Use lowercase 'user-agent'
    )
    await mill_client.async_setup()
    await mill_client.login()
    assert mill_client.access_token == "old_id_token"

    # 2. Mock response for a request that will trigger a 401 (token expired)
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_CUSTOMER_SETTINGS}",
        method="GET",
        status_code=401,
        json={"error": "Token expired"},
        match_headers={"Authorization": "Bearer old_id_token", "user-agent": USER_AGENT} # Use lowercase
    )

    # 3. Mock response for the *second* login attempt (triggered by force_refresh=True)
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_AUTH_SIGN_IN}", 
        method="POST",
        json={"idToken": "new_id_token", "refreshToken": "new_refresh_token"},
        status_code=200,
        match_headers={"user-agent": USER_AGENT} # Use lowercase
    )

    # 4. Mock response for the retried request *after* the successful "new" login
    httpx_mock.add_response(
        url=f"{BASE_URL}{ENDPOINT_CUSTOMER_SETTINGS}",
        method="GET",
        json={"houseList": []}, 
        status_code=200,
        match_headers={"Authorization": "Bearer new_id_token", "user-agent": USER_AGENT} # Use lowercase
    )
    
    response = await mill_client._request("GET", ENDPOINT_CUSTOMER_SETTINGS)
    assert response.status_code == 200
    assert mill_client.access_token == "new_id_token"
    
    await mill_client.async_close()