"""Test the ADS config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ads.config_flow import (
    CONF_DEVICE,
    CONF_IP_ADDRESS,
    CONF_PORT,
    ADSConfigFlow,
)


@pytest.mark.asyncio  # This is important for asyncio tests
class TestADSConfigFlow:
    """Test the ADSConfigFlow class."""

    @patch("homeassistant.components.ads.hub.AdsHub.test_connection")
    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_valid_ams_net_id(self, mock_create_entry, mock_test_connection):
        """Test if the flow correctly handles a valid AMS Net ID."""
        mock_test_connection.return_value = True

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        flow = ADSConfigFlow()
        flow.hass = hass

        # Simulate user input with valid AMS Net ID and other fields
        user_input = {
            CONF_DEVICE: "10.0.10.20.1.1",  # valid AMS Net ID
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "10.0.10.20",
        }
        # Mock the behavior of async_create_entry to return a dictionary with 'type' == 'create_entry'
        mock_create_entry.return_value = {"type": "create_entry"}

        result = await flow.async_step_user(user_input)

        # Check that async_create_entry was called with correct arguments
        mock_create_entry.assert_called_once_with(title="ADS", data=user_input)
        assert result["type"] == "create_entry"

    @patch("homeassistant.components.ads.hub.AdsHub.test_connection")
    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_invalid_ams_net_id(self, mock_create_entry, mock_test_connection):
        """Test if the flow handles invalid AMS Net ID input."""

        mock_test_connection.return_value = False  # Simulate failed connection

        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        flow = ADSConfigFlow()
        flow.hass = hass

        # Simulate user input with an invalid AMS Net ID
        user_input = {
            CONF_DEVICE: "10.0.10.20.1",  # Invalid AMS Net ID (missing last part)
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "10.0.10.20",
        }

        # Mock the behavior of async_create_entry to return None, meaning no entry is created
        mock_create_entry.return_value = None

        result = await flow.async_step_user(user_input)

        mock_create_entry.assert_not_called()

        # Ensure the flow doesn't create an entry and returns the error for the AMS Net ID
        assert result["type"] == "form"
        assert result["errors"] == {CONF_DEVICE: "invalid_ams_net_id"}

    @patch("homeassistant.components.ads.hub.AdsHub.test_connection")
    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_valid_input_creates_entry(
        self, mock_create_entry, mock_test_connection
    ):
        """Test if valid user input creates an entry."""

        mock_test_connection.return_value = False  # Simulate failed connection
        hass = MagicMock()
        hass.async_add_executor_job = AsyncMock()
        flow = ADSConfigFlow()
        flow.hass = hass

        # Mock the behavior of async_create_entry to return a dictionary with 'type' == 'create_entry'
        mock_create_entry.return_value = {"type": "create_entry"}

        # Valid user input
        user_input = {
            CONF_DEVICE: "10.0.10.20.1.1",  # valid AMS Net ID
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "10.0.10.20",
        }

        # # Call the user step with valid input
        result = await flow.async_step_user(user_input)

        # Check if an entry was created
        mock_create_entry.assert_called_once_with(title="ADS", data=user_input)
        assert result["type"] == "create_entry"

    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_invalid_port(self, mock_create_entry):
        """Test if the port validation works correctly."""

        flow = ADSConfigFlow()

        # Invalid port (outside the allowed range)
        user_input = {
            CONF_DEVICE: "10.0.10.20.1.1",
            CONF_PORT: 99999,  # Invalid port number (too large)
            CONF_IP_ADDRESS: "10.0.10.20",
        }

        result = await flow.async_step_user(user_input)

        mock_create_entry.assert_not_called()

        # # Ensure the flow returns an error for the port
        assert result["type"] == "form"
        assert result["errors"] == {CONF_PORT: "invalid_port"}

    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_missing_required_fields(self, mock_create_entry):
        """Test if missing required fields triggers an error."""

        flow = ADSConfigFlow()

        # Missing required field (device)
        user_input = {
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "192.168.1.100",
        }

        result = await flow.async_step_user(user_input)

        # Ensure that async_create_entry was not called due to missing fields
        mock_create_entry.assert_not_called()

        # Ensure the flow returns an error for missing device field
        assert result["type"] == "form"
        assert result["errors"] == {CONF_DEVICE: "required"}

    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_empty_device_name(self, mock_create_entry):
        """Test if empty device name raises the appropriate error."""

        flow = ADSConfigFlow()
        user_input = {
            CONF_DEVICE: "",
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "192.168.1.100",
        }

        result = await flow.async_step_user(user_input)

        # Ensure that the error for device is shown
        assert result["type"] == "form"
        assert result["errors"] == {CONF_DEVICE: "required"}

    @patch("homeassistant.config_entries.ConfigFlow.async_create_entry")
    async def test_invalid_ams_net_id_non_numeric(self, mock_create_entry):
        """Test providing a non-numeric AMS Net ID, which should raise a ValueError."""
        flow = ADSConfigFlow()

        user_input = {
            CONF_DEVICE: "192.168.abc.1.1.1",  # Non-numeric AMS Net ID
            CONF_PORT: 851,
            CONF_IP_ADDRESS: "192.168.1.100",
        }

        result = await flow.async_step_user(user_input)

        assert result["type"] == "form"
        assert result["errors"] == {CONF_DEVICE: "invalid_ams_net_id"}
