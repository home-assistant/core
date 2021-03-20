"""Define tests for the flunearyou config flow."""
from unittest.mock import patch

from pyflunearyou.errors import FluNearYouError

from homeassistant import data_entry_flow
from homeassistant.components.flunearyou import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that an error is shown when duplicates are added."""
    conf = {CONF_LATITUDE: "51.528308", CONF_LONGITUDE: "-0.3817765"}

    MockConfigEntry(
        domain=DOMAIN, unique_id="51.528308, -0.3817765", data=conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_general_error(hass):
    """Test that an error is shown on a library error."""
    conf = {CONF_LATITUDE: "51.528308", CONF_LONGITUDE: "-0.3817765"}

    with patch(
        "pyflunearyou.cdc.CdcReport.status_by_coordinates",
        side_effect=FluNearYouError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["errors"] == {"base": "unknown"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_LATITUDE: "51.528308", CONF_LONGITUDE: "-0.3817765"}

    with patch(
        "homeassistant.components.flunearyou.async_setup_entry", return_value=True
    ), patch("pyflunearyou.cdc.CdcReport.status_by_coordinates"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "51.528308, -0.3817765"
        assert result["data"] == {
            CONF_LATITUDE: "51.528308",
            CONF_LONGITUDE: "-0.3817765",
        }
