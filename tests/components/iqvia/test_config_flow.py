"""Define tests for the IQVIA config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.iqvia import CONF_ZIP_CODE, DOMAIN, config_flow

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_ZIP_CODE: "12345"}

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_ZIP_CODE: "identifier_exists"}


async def test_invalid_zip_code(hass):
    """Test that an invalid ZIP code key throws an error."""
    conf = {CONF_ZIP_CODE: "abcde"}

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_ZIP_CODE: "invalid_zip_code"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {CONF_ZIP_CODE: "12345"}

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import(import_config=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "12345"
    assert result["data"] == {CONF_ZIP_CODE: "12345"}


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_ZIP_CODE: "12345"}

    flow = config_flow.IQVIAFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "12345"
    assert result["data"] == {CONF_ZIP_CODE: "12345"}
