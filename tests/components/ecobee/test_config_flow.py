"""Tests for the ecobee config flow."""
from unittest.mock import patch

from pyecobee import ECOBEE_API_KEY, ECOBEE_REFRESH_TOKEN
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.ecobee import config_flow
from homeassistant.components.ecobee.const import (
    CONF_REFRESH_TOKEN,
    DATA_ECOBEE_CONFIG,
    DOMAIN,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_abort_if_already_setup(hass: HomeAssistant) -> None:
    """Test we abort if ecobee is already setup."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass

    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_user_step_without_user_input(hass: HomeAssistant) -> None:
    """Test expected result if user step is called."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_pin_request_succeeds(hass: HomeAssistant) -> None:
    """Test expected result if pin request succeeds."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.request_pin.return_value = True
        mock_ecobee.pin = "test-pin"

        result = await flow.async_step_user(user_input={CONF_API_KEY: "api-key"})

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert result["description_placeholders"] == {"pin": "test-pin"}


async def test_pin_request_fails(hass: HomeAssistant) -> None:
    """Test expected result if pin request fails."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.request_pin.return_value = False

        result = await flow.async_step_user(user_input={CONF_API_KEY: "api-key"})

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"]["base"] == "pin_request_failed"


async def test_token_request_succeeds(hass: HomeAssistant) -> None:
    """Test expected result if token request succeeds."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.request_tokens.return_value = True
        mock_ecobee.api_key = "test-api-key"
        mock_ecobee.refresh_token = "test-token"

        flow._ecobee = mock_ecobee

        result = await flow.async_step_authorize(user_input={})

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DOMAIN
        assert result["data"] == {
            CONF_API_KEY: "test-api-key",
            CONF_REFRESH_TOKEN: "test-token",
        }


async def test_token_request_fails(hass: HomeAssistant) -> None:
    """Test expected result if token request fails."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    with patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.request_tokens.return_value = False
        mock_ecobee.pin = "test-pin"

        flow._ecobee = mock_ecobee

        result = await flow.async_step_authorize(user_input={})

        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "authorize"
        assert result["errors"]["base"] == "token_request_failed"
        assert result["description_placeholders"] == {"pin": "test-pin"}


@pytest.mark.skip(reason="Flaky/slow")
async def test_import_flow_triggered_but_no_ecobee_conf(hass: HomeAssistant) -> None:
    """Test expected result if import flow triggers but ecobee.conf doesn't exist."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {}

    result = await flow.async_step_import(import_data=None)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_import_flow_triggered_with_ecobee_conf_and_valid_data_and_valid_tokens(
    hass: HomeAssistant,
) -> None:
    """Test expected result if import flow triggers and ecobee.conf exists with valid tokens."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass

    MOCK_ECOBEE_CONF = {ECOBEE_API_KEY: None, ECOBEE_REFRESH_TOKEN: None}

    with patch(
        "homeassistant.components.ecobee.config_flow.load_json_object",
        return_value=MOCK_ECOBEE_CONF,
    ), patch("homeassistant.components.ecobee.config_flow.Ecobee") as mock_ecobee:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.refresh_tokens.return_value = True
        mock_ecobee.api_key = "test-api-key"
        mock_ecobee.refresh_token = "test-token"

        result = await flow.async_step_import(import_data=None)

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == DOMAIN
        assert result["data"] == {
            CONF_API_KEY: "test-api-key",
            CONF_REFRESH_TOKEN: "test-token",
        }


async def test_import_flow_triggered_with_ecobee_conf_and_invalid_data(
    hass: HomeAssistant,
) -> None:
    """Test expected result if import flow triggers and ecobee.conf exists with invalid data."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {CONF_API_KEY: "test-api-key"}

    MOCK_ECOBEE_CONF = {}

    with patch(
        "homeassistant.components.ecobee.config_flow.load_json_object",
        return_value=MOCK_ECOBEE_CONF,
    ), patch.object(flow, "async_step_user") as mock_async_step_user:
        await flow.async_step_import(import_data=None)

        mock_async_step_user.assert_called_once_with(
            user_input={CONF_API_KEY: "test-api-key"}
        )


async def test_import_flow_triggered_with_ecobee_conf_and_valid_data_and_stale_tokens(
    hass: HomeAssistant,
) -> None:
    """Test expected result if import flow triggers and ecobee.conf exists with stale tokens."""
    flow = config_flow.EcobeeFlowHandler()
    flow.hass = hass
    flow.hass.data[DATA_ECOBEE_CONFIG] = {CONF_API_KEY: "test-api-key"}

    MOCK_ECOBEE_CONF = {ECOBEE_API_KEY: None, ECOBEE_REFRESH_TOKEN: None}

    with patch(
        "homeassistant.components.ecobee.config_flow.load_json_object",
        return_value=MOCK_ECOBEE_CONF,
    ), patch(
        "homeassistant.components.ecobee.config_flow.Ecobee"
    ) as mock_ecobee, patch.object(flow, "async_step_user") as mock_async_step_user:
        mock_ecobee = mock_ecobee.return_value
        mock_ecobee.refresh_tokens.return_value = False

        await flow.async_step_import(import_data=None)

        mock_async_step_user.assert_called_once_with(
            user_input={CONF_API_KEY: "test-api-key"}
        )
