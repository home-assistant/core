"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.async_mock import create_autospec, patch


@pytest.fixture(name="account")
def mock_account(spa):
    """Mock a SmartTub.Account."""

    mock_account = create_autospec(smarttub.Account, instance=True)
    mock_account.id = "mockaccount1"
    mock_account.get_spas.return_value = [spa]
    return mock_account


@pytest.fixture(name="smarttub_api")
def mock_api(account):
    """Mock the SmartTub API."""

    with patch(
        "homeassistant.components.smarttub.controller.SmartTub",
        autospec=True,
    ) as api_class_mock:
        api_mock = api_class_mock.return_value
        api_mock.get_account.return_value = account
        yield api_mock


@pytest.fixture(name="controller")
async def make_controller(hass, smarttub_api, config_entry):
    """Instantiate the controller for testing."""

    controller = SmartTubController(hass)
    assert len(controller.spas) == 0

    ret = await controller.async_setup_entry(config_entry)
    assert ret is True
    assert len(controller.spas) > 0

    return controller


async def test_unload(controller, config_entry):
    """Test async_unload_entry."""
    ret = await controller.async_unload_entry(config_entry)
    assert ret is True


async def test_invalid_credentials(hass, controller, smarttub_api, config_entry):
    """Check that we start a new config flow if the configured credentials are invalid.

    This should mean that the user changed their SmartTub password.
    """

    smarttub_api.login.side_effect = smarttub.LoginFailed
    controller = SmartTubController(hass)
    ret = await controller.async_setup_entry(config_entry)
    assert ret is False


async def test_update(controller, spa):
    """Test data updates from API."""
    data = await controller.async_update_data()
    assert data[spa.id] == {"status": spa.get_status.return_value}

    spa.get_status.side_effect = smarttub.APIError
    with pytest.raises(UpdateFailed):
        data = await controller.async_update_data()


async def test_get_account_id(controller, smarttub_api):
    """Test SmartTubController.validate_credentials."""
    smarttub_api.get_account.return_value.id = "account-id1"
    account_id = await controller.get_account_id("test-email1", "test-password1")
    smarttub_api.login.assert_called()
    assert account_id == "account-id1"

    smarttub_api.login.side_effect = smarttub.LoginFailed
    account_id = await controller.get_account_id("test-email1", "test-password1")
    assert account_id is None
