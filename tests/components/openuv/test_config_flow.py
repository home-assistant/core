"""Define tests for the OpenUV config flow."""
from pyopenuv.errors import InvalidApiKeyError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.openuv import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup():
    """Prevent setup."""
    with patch(
        "homeassistant.components.openuv.async_setup", return_value=True,
    ), patch(
        "homeassistant.components.openuv.async_setup_entry", return_value=True,
    ):
        yield


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    MockConfigEntry(
        domain=DOMAIN, unique_id="39.128712, -104.9812612", data=conf
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_api_key(hass):
    """Test that an invalid API key throws an error."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    with patch(
        "pyopenuv.client.Client.uv_index", side_effect=InvalidApiKeyError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_API_KEY: "invalid_api_key"}


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_API_KEY: "12345abcde",
        CONF_ELEVATION: 59.1234,
        CONF_LATITUDE: 39.128712,
        CONF_LONGITUDE: -104.9812612,
    }

    with patch(
        "homeassistant.components.airvisual.async_setup_entry", return_value=True
    ), patch("pyopenuv.client.Client.uv_index"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "39.128712, -104.9812612"
        assert result["data"] == {
            CONF_API_KEY: "12345abcde",
            CONF_ELEVATION: 59.1234,
            CONF_LATITUDE: 39.128712,
            CONF_LONGITUDE: -104.9812612,
        }
