"""Define tests for the FMI config flow."""

from unittest.mock import patch

from fmi_weather_client.errors import ClientError

from homeassistant import data_entry_flow
from homeassistant.components.fmi.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME, CONF_OFFSET

from .const import MOCK_CURRENT

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_OFFSET: 12,
    CONF_LATITUDE: 55.55,
    CONF_LONGITUDE: 122.12,
}

INVALID_CONFIG = {
    CONF_NAME: "abcd",
    CONF_OFFSET: 12,
    CONF_LATITUDE: 0,
    CONF_LONGITUDE: 0,
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
        "homeassistant.components.fmi.config_flow.fmi_client.weather_by_coordinates",
        side_effect=ClientError(status_code=404, message="API error"),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=INVALID_CONFIG,
        )

        assert result["errors"] == {}


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    with patch(
        "homeassistant.components.fmi.config_flow.fmi_client.weather_by_coordinates",
        return_value=MOCK_CURRENT,
    ):

        MockConfigEntry(
            domain=DOMAIN,
            unique_id="55.55_122.12",
            data=VALID_CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.fmi.config_flow.fmi_client.weather_by_coordinates",
        return_value=MOCK_CURRENT,
    ), patch(
        "homeassistant.components.fmi.config_flow.fmi_client.weather_by_coordinates",
        return_value=MOCK_CURRENT,
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "MOON"
        assert result["data"][CONF_NAME] == "abcd"
        assert result["data"][CONF_LATITUDE] == 55.55
        assert result["data"][CONF_LONGITUDE] == 122.12
        assert result["data"][CONF_OFFSET] == 12
