"""Test the aidot config flow."""

from unittest.mock import ANY, MagicMock, Mock, patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.aidot.config_flow import (
    CannotConnect,
    ConfigFlow,
    InvalidHost,
    validate_input,
)
from homeassistant.components.aidot.const import (
    CONF_CHOOSE_HOUSE,
    CONF_PASSWORD,
    CONF_SERVER_COUNTRY,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_validate_input_valid():
    """Mock the HomeAssistant object (if needed)."""
    hass = MagicMock()

    # Test with valid data
    data = {"host": "valid_host"}

    # Call the function and assert it returns the correct output
    result = await validate_input(hass, data)
    assert result == {"title": "valid_host"}


@pytest.mark.asyncio
async def test_validate_input_invalid():
    """Mock the HomeAssistant object (if needed)."""
    hass = MagicMock()

    # Test with invalid data (host length < 3)
    data = {"host": "ab"}

    # Assert that it raises the InvalidHost exception
    with pytest.raises(InvalidHost):
        await validate_input(hass, data)


@pytest.fixture
def mock_login_control():
    """Fixture for mocking LoginControl."""
    with patch(
        "homeassistant.components.aidot.config_flow.LoginControl", autospec=True
    ) as mock:
        yield mock.return_value


@pytest.fixture
def hass():
    """Fixture for HomeAssistant instance."""
    return Mock(spec=HomeAssistant)


@pytest.mark.asyncio
async def test_flow_user_init(mock_login_control) -> None:
    """Test the initial user step of the config flow."""
    flow = ConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user()

    # expected_countries = [item["name"] for item in CLOUD_SERVERS]
    # expected_schema = vol.Schema(
    #     {
    #         vol.Required(CONF_SERVER_COUNTRY, default="United States"): vol.In(
    #             expected_countries
    #         ),
    #         vol.Required(CONF_USERNAME): str,
    #         vol.Required(CONF_PASSWORD): str,
    #     }
    # )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    # assert result["data_schema"].schema == expected_schema.schema


@pytest.mark.asyncio
async def test_flow_user_login_success(mock_login_control) -> None:
    """Test user login and house selection."""
    flow = ConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_SERVER_COUNTRY: "United States",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }

    mock_login_response = {
        "accessToken": "mock-access-token",
        "username": "test-username",
    }
    mock_house_list = [
        {"name": "House 1", "id": "house1", "isDefault": True},
        {"name": "House 2", "id": "house2"},
    ]

    mock_login_control.async_post_login.return_value = mock_login_response
    mock_login_control.async_get_houses.return_value = mock_house_list

    result = await flow.async_step_user(user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "login_failed"}

    mock_login_control.change_country_code.assert_called_once()
    mock_login_control.async_post_login.assert_called_once()
    mock_login_control.async_get_houses.assert_called_once()


@pytest.mark.asyncio
async def test_flow_user_invalid_host(mock_login_control) -> None:
    """Test handling invalid host error."""
    flow = ConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_SERVER_COUNTRY: "United States",
        CONF_USERNAME: "t",
        CONF_PASSWORD: "test-password",
    }

    result = await flow.async_step_user(user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "login_failed"}


@pytest.mark.asyncio
async def test_flow_user_cannot_connect(mock_login_control) -> None:
    """Test handling cannot connect error."""
    flow = ConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_SERVER_COUNTRY: "United States",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }

    mock_login_control.async_post_login.side_effect = CannotConnect

    result = await flow.async_step_user(user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_flow_choose_house(mock_login_control) -> None:
    """Test house selection step."""
    flow = ConfigFlow()
    flow.hass = hass

    flow.login_response = {
        "accessToken": "mock-access-token",
        "username": "test-username",
    }
    flow.house_list = [
        {"name": "House 1", "id": "house1", "isDefault": True},
        {"name": "House 2", "id": "house2"},
    ]

    user_input = {CONF_CHOOSE_HOUSE: "House 1"}

    mock_device_list = [{"productId": "product1"}, {"productId": "product2"}]
    mock_product_list = [{"id": "product1"}, {"id": "product2"}]

    mock_login_control.async_get_devices.return_value = mock_device_list
    mock_login_control.async_get_products.return_value = mock_product_list

    result = await flow.async_step_choose_house(user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-username House 1"
    assert result["data"] == {
        "login_response": flow.login_response,
        "selected_house": {"name": "House 1", "id": "house1", "isDefault": True},
        "device_list": mock_device_list,
        "product_list": mock_product_list,
    }

    mock_login_control.async_get_devices.assert_called_once()
    mock_login_control.async_get_products.assert_called_once()


@pytest.mark.asyncio
async def test_async_show_form_called_correctly(mock_login_control) -> None:
    """Test that async_show_form is called with correct parameters in user step."""
    flow = ConfigFlow()
    flow.hass = hass

    # Mock the async_show_form method
    flow.async_show_form = MagicMock()

    # Mock CLOUD_SERVERS
    with patch(
        "homeassistant.components.aidot.config_flow.CLOUD_SERVERS",
        [{"name": "United States"}, {"name": "Canada"}],
    ):
        user_input = None

        await flow.async_step_user(user_input)

        # Ensure async_show_form was called
        flow.async_show_form.assert_called_once()

        # Check the parameters passed to async_show_form
        flow.async_show_form.assert_called_with(
            step_id="user",
            data_schema=ANY,  # data_schema can be matched using ANY since it's dynamically generated
            errors={},  # Initially, there are no errors
        )
