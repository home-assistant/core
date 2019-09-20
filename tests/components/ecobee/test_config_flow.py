"""Tests for the ecobee config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.ecobee import config_flow
from homeassistant.components.ecobee.const import (
    CONF_REFRESH_TOKEN,
    DATA_ECOBEE_CONFIG,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY


async def test_abort_if_already_setup(hass):
    """Test we abort if ecobee is already setup."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass

    with patch.object(hass.config_entries, "async_entries", return_value=[{}]):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "one_instance_only"


async def test_user_step_without_user_input(hass):
    """Test expected result if user step is called."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_pin_request_succeeds(hass):
    """Test expected result if pin request succeeds."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as MockEcobee:
        mock_ecobee = MockEcobee.return_value
        mock_ecobee.request_pin.return_value = True
        mock_ecobee.pin = "test-pin"

        result = await flow.async_step_user(user_input={CONF_API_KEY: "api-key"})

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "authorize"
        assert result["description_placeholders"] == {"pin": "test-pin"}


async def test_pin_request_fails(hass):
    """Test expected result if pin request fails."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as MockEcobee:
        mock_ecobee = MockEcobee.return_value
        mock_ecobee.request_pin.return_value = False

        result = await flow.async_step_user(user_input={CONF_API_KEY: "api-key"})

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "pin_request_failed"


async def test_token_request_succeeds(hass):
    """Test expected result if token request succeeds."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as MockEcobee:
        mock_ecobee = MockEcobee.return_value
        mock_ecobee.request_tokens.return_value = True
        mock_ecobee.api_key = "test-api-key"
        mock_ecobee.refresh_token = "test-token"
        flow._ecobee = mock_ecobee

        result = await flow.async_step_authorize(user_input={})

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == DOMAIN
        assert result["data"] == {
            CONF_API_KEY: "test-api-key",
            CONF_REFRESH_TOKEN: "test-token",
        }


async def test_token_request_fails(hass):
    """Test expected result if token request fails."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as MockEcobee:
        mock_ecobee = MockEcobee.return_value
        mock_ecobee.request_tokens.return_value = False
        mock_ecobee.pin = "test-pin"
        flow._ecobee = mock_ecobee

        result = await flow.async_step_authorize(user_input={})

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "authorize"
        assert result["errors"]["base"] == "token_request_failed"
        assert result["description_placeholders"] == {"pin": "test-pin"}
