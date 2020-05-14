"""Define tests for the Airly config flow."""
import json

from airly.exceptions import AirlyError
from asynctest import patch

from homeassistant import data_entry_flow
from homeassistant.components.airly.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    HTTP_FORBIDDEN,
)

from tests.common import MockConfigEntry, load_fixture

CONFIG = {
    CONF_NAME: "abcd",
    CONF_API_KEY: "foo",
    CONF_LATITUDE: 123,
    CONF_LONGITUDE: 456,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_api_key(hass):
    """Test that errors are shown when API key is invalid."""
    with patch(
        "airly._private._RequestsHandler.get",
        side_effect=AirlyError(
            HTTP_FORBIDDEN, {"message": "Invalid authentication credentials"}
        ),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "auth"}


async def test_invalid_location(hass):
    """Test that errors are shown when location is invalid."""
    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_no_station.json")),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {"base": "wrong_location"}


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):
        MockConfigEntry(domain=DOMAIN, unique_id="123-456", data=CONFIG).add_to_hass(
            hass
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_create_entry(hass):
    """Test that the user step works."""

    with patch(
        "airly._private._RequestsHandler.get",
        return_value=json.loads(load_fixture("airly_valid_station.json")),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == CONFIG[CONF_NAME]
        assert result["data"][CONF_LATITUDE] == CONFIG[CONF_LATITUDE]
        assert result["data"][CONF_LONGITUDE] == CONFIG[CONF_LONGITUDE]
        assert result["data"][CONF_API_KEY] == CONFIG[CONF_API_KEY]
