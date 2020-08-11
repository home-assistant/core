"""Define tests for the IQVIA config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.iqvia import CONF_ZIP_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_ZIP_CODE: "12345"}

    MockConfigEntry(domain=DOMAIN, unique_id="12345", data=conf).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_zip_code(hass):
    """Test that an invalid ZIP code key throws an error."""
    conf = {CONF_ZIP_CODE: "abcde"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_ZIP_CODE: "invalid_zip_code"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass):
    """Test that the user step works (without MFA)."""
    conf = {CONF_ZIP_CODE: "12345"}

    with patch(
        "homeassistant.components.simplisafe.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "12345"
        assert result["data"] == {CONF_ZIP_CODE: "12345"}
