"""Define tests for the IQVIA config flow."""

from homeassistant.components.iqvia import CONF_ZIP_CODE, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_duplicate_error(hass: HomeAssistant, config, config_entry) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_zip_code(hass: HomeAssistant) -> None:
    """Test that an invalid ZIP code key throws an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_ZIP_CODE: "bad"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ZIP_CODE: "invalid_zip_code"}


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass: HomeAssistant, config, setup_iqvia) -> None:
    """Test that the user step works (without MFA)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "12345"
    assert result["data"] == {CONF_ZIP_CODE: "12345"}
