"""Test the Azure DevOps config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.azure_devops import config_flow
from homeassistant.components.azure_devops.const import CONF_ORG, CONF_PAT, CONF_PROJECT

USER_INPUT_BAD = {
    CONF_ORG: "example",
    CONF_PROJECT: "something",
    CONF_PAT: "abcdef",
}

USER_INPUT = {CONF_ORG: "ms", CONF_PROJECT: "calculator"}


async def test_show_form(hass):
    """Test that the setup form is served."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_authorization_error(hass):
    """Test we show user form on Azure DevOps connection error."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=USER_INPUT_BAD)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "authorization_error"}


async def test_full_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    flow = config_flow.AzureDevOpsFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await flow.async_step_user(user_input=USER_INPUT)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{USER_INPUT[CONF_ORG]}/{USER_INPUT[CONF_PROJECT]}"
    assert result["data"][CONF_ORG] == USER_INPUT[CONF_ORG]
    assert result["data"][CONF_PROJECT] == USER_INPUT[CONF_PROJECT]
