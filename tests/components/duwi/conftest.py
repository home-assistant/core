"""Define common test fixtures for the Duwi integration."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from duwi_smarthome_sdk.const.status import Code


@pytest.fixture
def mock_duwi_login_auth() -> Generator[AsyncMock, None, None]:
    """Mock the Duwi login authentication process.

    This fixture simulates the authentication process for the Duwi smart
    home SDK, returning a success code and mocked tokens for valid credentials,
    and an error code for invalid ones.
    """

    async def mock_auth_func(phone: str, password: str):
        # Simulate successful authentication
        if phone == "correct_phone" and password == "correct_password":
            return Code.SUCCESS.value, MagicMock(
                access_token="mocked_access_token",
                access_token_expire_time="mocked_access_token_expire_time",
                refresh_token="mocked_refresh_token",
                refresh_token_expire_time="mocked_refresh_token_expire_time",
            )
        # Simulate failed authentication
        else:
            return Code.LOGIN_ERROR.value, None

    with patch(
        "duwi_smarthome_sdk.api.account.AccountClient.login", new_callable=MagicMock
    ) as mock_auth:
        mock_auth.side_effect = mock_auth_func
        yield mock_auth


@pytest.fixture
def mock_duwi_login_user() -> Generator[AsyncMock, None, None]:
    """Mock the Duwi user login process.

    This fixture is intended to simulate different login responses based on
    the provided application key and secret.
    """

    async def mock_login_func(app_key: str, app_secret: str):
        # Define login logic simulation based on app_key and app_secret combinations
        if app_key == "correct_app_key" and app_secret == "correct_app_secret":
            return Code.SUCCESS.value
        elif app_key == "error_app_key" and app_secret == "correct_app_secret":
            return Code.APP_KEY_ERROR.value
        elif app_key == "correct_app_key" and app_secret == "error_app_secret":
            return Code.SIGN_ERROR.value

    with patch(
        "duwi_smarthome_sdk.api.account.AccountClient.auth", new_callable=MagicMock
    ) as mock_login:
        mock_login.side_effect = mock_login_func
        yield mock_login


@pytest.fixture
def mock_duwi_login_select_house() -> Generator[AsyncMock, None, None]:
    """Mock the Duwi house selection control process.

    This fixture mimics the house selection process, providing a simulated
    list of house information.
    """

    async def mock_select_house_func():
        # Simulate house selection response
        return Code.SUCCESS.value, [
            MagicMock(
                house_no="house_nos_123",
                house_name="house_name_123",
                house_image_url="house_image_url_123",
                address="address_123",
                location="location_123",
                seq=1,
                create_time="create_time_123",
                deliver_time="deliver_time_123",
                host_count=1,
                device_count=1,
                lan_secret_key="lan_secret_key_123",
            )
        ]

    with patch(
        "duwi_smarthome_sdk.api.house.HouseInfoClient.fetch_house_info",
        new_callable=MagicMock,
    ) as mock_select_house:
        mock_select_house.side_effect = mock_select_house_func
        yield mock_select_house
