"""Test the SmartTub controller."""

import pytest
import smarttub

from homeassistant.components.smarttub.controller import SmartTubController
from homeassistant.helpers.update_coordinator import UpdateFailed


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
