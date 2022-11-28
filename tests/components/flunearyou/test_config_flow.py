"""Define tests for the flunearyou config flow."""
from unittest.mock import patch

from pyflunearyou.errors import FluNearYouError

from homeassistant import data_entry_flow
from homeassistant.components.flunearyou import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE


async def test_duplicate_error(hass, config, config_entry, setup_flunearyou):
    """Test that an error is shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_errors(hass, config):
    """Test that exceptions show the appropriate error."""
    with patch(
        "pyflunearyou.cdc.CdcReport.status_by_coordinates", side_effect=FluNearYouError
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["errors"] == {"base": "unknown"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, config, setup_flunearyou):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "51.528308, -0.3817765"
    assert result["data"] == {
        CONF_LATITUDE: 51.528308,
        CONF_LONGITUDE: -0.3817765,
    }
