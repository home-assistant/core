"""Define common test fixtures for the Duwi integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from duwi_smarthome_sdk.const import DuwiCode
import pytest


@pytest.fixture
def mock_duwi_login_user() -> Generator[AsyncMock, None, None]:
    """Mock the Duwi login authentication process."""

    async def mock_auth_func(phone: str, password: str):
        # Simulate successful authentication
        if phone == "correct_phone" and password == "correct_password":
            return {
                "code": DuwiCode.SUCCESS.value,
                "data": {
                    "access_token": "mocked_access_token",
                    "access_token_expire_time": "mocked_access_token_expire_time",
                    "refresh_token": "mocked_refresh_token",
                    "refresh_token_expire_time": "mocked_refresh_token_expire_time",
                },
            }
        # Simulate failed authentication
        return {"code": DuwiCode.LOGIN_ERROR.value, "data": {}}

    with patch(
        "duwi_smarthome_sdk.manager.CustomerClient.login", new_callable=AsyncMock
    ) as mock_auth:
        mock_auth.side_effect = mock_auth_func
        yield mock_auth


@pytest.fixture
def mock_duwi_login_and_fetch_house() -> Generator[AsyncMock, None, None]:
    """Mock the Duwi login authentication process and house info fetching."""

    async def mock_fetch_house_info():
        # Simulate successful house info fetching
        return {
            "code": DuwiCode.SUCCESS.value,
            "data": {
                "houseInfos": [
                    {
                        "houseNo": "mocked_house_no1",
                        "houseName": "mocked_house_name1",
                        "lanSecretKey": "mocked_lan_secret_key1",
                    },
                    {
                        "houseNo": "mocked_house_no2",
                        "houseName": "mocked_house_name2",
                        "lanSecretKey": "mocked_lan_secret_key2",
                    },
                ]
            },
        }

    with patch(
        "duwi_smarthome_sdk.manager.CustomerClient.fetch_house_info",
        new_callable=AsyncMock,
    ) as mock_fetch:
        # Set side effects for mocks
        mock_fetch.side_effect = mock_fetch_house_info

        yield mock_fetch


@pytest.fixture
def mock_duwi_fetch_house_info_error():
    """Mock fetch_house_info to simulate an error response."""
    with patch(
        "duwi_smarthome_sdk.customer_client.CustomerClient.fetch_house_info"
    ) as mock_fetch_house_info:
        # Simulate an error response with a code different from SUCCESS
        mock_fetch_house_info.return_value = {
            "code": DuwiCode.SYS_ERROR.value,
            "message": "System error while fetching house info",
        }
        yield mock_fetch_house_info


@pytest.fixture
def mock_duwi_no_houses_found():
    """Mock fetch_house_info to return no houses."""
    with patch(
        "duwi_smarthome_sdk.customer_client.CustomerClient.fetch_house_info"
    ) as mock_fetch_house_info:
        # Simulate a successful response but with no houses found
        mock_fetch_house_info.return_value = {
            "code": DuwiCode.SUCCESS.value,
            "data": {
                "houseInfos": [],  # Empty list to simulate no houses
            },
        }
        yield mock_fetch_house_info


@pytest.fixture
def mock_duwi_login_invalid_auth():
    """Mock the login function to simulate invalid authentication (e.g., wrong credentials)."""
    with patch("duwi_smarthome_sdk.customer_client.CustomerClient.login") as mock_login:
        mock_login.return_value = {
            "code": DuwiCode.LOGIN_ERROR.value,  # This should match your defined LOGIN_ERROR code
        }
        yield mock_login


@pytest.fixture
def mock_duwi_login_sys_error():
    """Mock the login function to simulate a system error."""
    with patch("duwi_smarthome_sdk.customer_client.CustomerClient.login") as mock_login:
        mock_login.return_value = {
            "code": DuwiCode.SYS_ERROR.value,  # This should match your defined SYS_ERROR code
        }
        yield mock_login
