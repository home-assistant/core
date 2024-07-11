"""Test the aidot config flow."""

from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from homeassistant import config_entries
from homeassistant.components.aidot.config_flow import CannotConnect, ConfigFlow
from homeassistant.components.aidot.const import (
    CONF_PASSWORD,
    CONF_SERVER_COUNTRY,
    CONF_USERNAME,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_COUNTRY, TEST_EMAIL, TEST_PASSWORD

MOCK_USER_INPUT = {
    "server_country": "United States",
    "username": "test_user",
    "password": "test_password",
}

MOCK_LOGIN_RESPONSE = {
    "accessToken": "mock_access_token",
    "username": "test_user",
}

MOCK_HOUSE_LIST = [
    {"id": 1, "name": "House 1", "isDefault": True},
    {"id": 2, "name": "House 2", "isDefault": False},
]

MOCK_DEVICE_LIST = [
    {"id": 101, "name": "Device 1", "productId": "prod_1"},
    {"id": 102, "name": "Device 2", "productId": "prod_2"},
]

MOCK_PRODUCT_LIST = [
    {"productId": "prod_1", "name": "Product 1"},
    {"productId": "prod_2", "name": "Product 2"},
]


@pytest.fixture
def mock_hass():
    """Fixture for creating a mock Home Assistant instance."""
    return Mock()


@pytest.fixture
def mock_login_control():
    """Fixture for creating a mock login control object using MagicMock."""
    return MagicMock()


@pytest.fixture
def config_flow(mock_hass, mock_login_control):
    """Fixture for creating a ConfigFlow instance with mocked Home Assistant and login control."""
    flow = ConfigFlow()
    flow.hass = mock_hass
    flow.__login_control = mock_login_control
    return flow


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_SERVER_COUNTRY: TEST_COUNTRY,
            CONF_USERNAME: TEST_EMAIL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == "form"
    assert result2["errors"]["base"] == "login_failed"


async def test_async_step_user_success(config_flow, mock_hass, mock_login_control):
    """Test async step user success."""
    mock_hass.async_create_task = AsyncMock()
    mock_login_control.async_post_login = AsyncMock(return_value=MOCK_LOGIN_RESPONSE)
    mock_login_control.async_get_houses = AsyncMock(return_value=MOCK_HOUSE_LIST)

    result = await config_flow.async_step_user(MOCK_USER_INPUT)

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_async_step_user_cannot_connect(
    config_flow, mock_hass, mock_login_control
):
    """Test async step user cannot connect."""
    mock_login_control.async_post_login = Mock(side_effect=CannotConnect)

    result = await config_flow.async_step_user(MOCK_USER_INPUT)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "login_failed"}


async def test_async_step_user_unexpected_exception(
    config_flow, mock_hass, mock_login_control
):
    """Test async step user unexpected exception."""
    mock_login_control.async_post_login = Mock(side_effect=Exception)

    result = await config_flow.async_step_user(MOCK_USER_INPUT)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "login_failed"}
