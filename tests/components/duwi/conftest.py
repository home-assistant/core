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
