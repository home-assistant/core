"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_invalid_credentials(hass, controller, smarttub_api, config_entry):
    """Check that we return False if the configured credentials are invalid.

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


async def test_login(controller, smarttub_api, account):
    """Test SmartTubController.login."""
    smarttub_api.get_account.return_value.id = "account-id1"
    account = await controller.login("test-email1", "test-password1")
    smarttub_api.login.assert_called()
    assert account == account
