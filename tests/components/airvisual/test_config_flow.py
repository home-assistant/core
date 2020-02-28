"""Define tests for the AirVisual config flow."""
from unittest.mock import patch

from pyairvisual.errors import InvalidKeyError

from homeassistant import data_entry_flow
from homeassistant.components.airvisual import CONF_GEOGRAPHIES, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE

from tests.common import MockConfigEntry, mock_coro


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_API_KEY: "abcde12345"}

    MockConfigEntry(domain=DOMAIN, unique_id="abcde12345", data=conf).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_api_key(hass):
    """Test that invalid credentials throws an error."""
    conf = {CONF_API_KEY: "abcde12345"}

    with patch(
        "pyairvisual.api.API.nearest_city",
        return_value=mock_coro(exception=InvalidKeyError),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {CONF_API_KEY: "abcde12345"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Cloud API (API key: abcd...)"
    assert result["data"] == {
        CONF_API_KEY: "abcde12345",
        CONF_GEOGRAPHIES: [{CONF_LATITUDE: 32.87336, CONF_LONGITUDE: -117.22743}],
    }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: "abcde12345",
        CONF_LATITUDE: 32.87336,
        CONF_LONGITUDE: -117.22743,
    }

    with patch(
        "pyairvisual.api.API.nearest_city", return_value=mock_coro(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Cloud API (API key: abcd...)"
        assert result["data"] == {
            CONF_API_KEY: "abcde12345",
            CONF_GEOGRAPHIES: [{CONF_LATITUDE: 32.87336, CONF_LONGITUDE: -117.22743}],
        }
