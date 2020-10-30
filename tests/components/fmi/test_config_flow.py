"""Define tests for the FMI config flow."""

from fmi_weather_client.errors import ClientError

from homeassistant import data_entry_flow
from homeassistant.components.fmi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_OFFSET

from .const import MOCK_CURRENT

from tests.async_mock import patch
from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_OFFSET: 12,
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 122.12,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_api_error(hass):
    """Test API error."""
    with patch(
        "fmi.weather_by_coordinates",
        side_effect=ClientError("Invalid response from FMI API"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["errors"] == {"base": "cannot_connect"}


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    with patch(
        "fmi.weather_by_coordinates",
        return_value=MOCK_CURRENT,
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="12.34567_76.54321",
            data=VALID_CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "fmi.weather_by_coordinates",
        return_value=MOCK_CURRENT,
    ), patch("homeassistant.components.fmi.weather_by_coordinates", return_value=True):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "MOON"
        assert result["data"][CONF_NAME] == "MOON"
        assert result["data"][CONF_LATITUDE] == 12.34567
        assert result["data"][CONF_LONGITUDE] == 76.54321
        assert result["data"][CONF_OFFSET] == 12
