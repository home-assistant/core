"""Test the Azure DevOps config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.azure_devops import config_flow
from homeassistant.components.azure_devops.const import CONF_ORG, CONF_PAT, CONF_PROJECT
from homeassistant.core import HomeAssistant

FIXTURE_USER_INPUT_BAD = {
    CONF_ORG: "example",
    CONF_PROJECT: "something",
    CONF_PAT: "abcdef",
}

FIXTURE_USER_INPUT = {CONF_ORG: "ms", CONF_PROJECT: "calculator"}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_authorization_error(hass: HomeAssistant) -> None:
    """Test we show user form on Azure DevOps authorization error."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT_BAD)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "authorization_error"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on Azure DevOps connection error."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass

    with patch(
        "homeassistant.components.azure_devops.config_flow.AzureDevOpsFlowHandler._test_connection",
        return_value=_return_connection_error(),
    ):
        result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "connection_error"}


async def _return_connection_error() -> str:
    return "connection_error"


async def test_full_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert (
        result["title"]
        == f"{FIXTURE_USER_INPUT[CONF_ORG]}/{FIXTURE_USER_INPUT[CONF_PROJECT]}"
    )
    assert result["data"][CONF_ORG] == FIXTURE_USER_INPUT[CONF_ORG]
    assert result["data"][CONF_PROJECT] == FIXTURE_USER_INPUT[CONF_PROJECT]
