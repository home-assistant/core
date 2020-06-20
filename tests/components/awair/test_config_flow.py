"""Define tests for the Awair config flow."""

from asynctest import patch
from python_awair.exceptions import AuthError, AwairError

from homeassistant import data_entry_flow
from homeassistant.components.awair.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ACCESS_TOKEN

from .const import (
    CONFIG,
    CONFIG_ENTRY_UNIQUE_ID,
    DEVICES_FIXTURE,
    NO_DEVICES_FIXTURE,
    USER_FIXTURE,
)

from tests.common import MockConfigEntry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_access_token(hass):
    """Test that errors are shown when the access token is invalid."""

    with patch("python_awair.AwairClient.query", side_effect=AuthError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["errors"] == {CONF_ACCESS_TOKEN: "auth"}


async def test_unexpected_api_error(hass):
    """Test that we abort on generic errors."""

    with patch("python_awair.AwairClient.query", side_effect=AwairError()):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "unknown"


async def test_duplicate_error(hass):
    """Test that errors are shown when adding a duplicate config."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ):
        MockConfigEntry(
            domain=DOMAIN, unique_id=CONFIG_ENTRY_UNIQUE_ID, data=CONFIG
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


async def test_no_devices_error(hass):
    """Test that errors are shown when the API returns no devices."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, NO_DEVICES_FIXTURE]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == "abort"
        assert result["reason"] == "no_devices"


async def test_create_entry(hass):
    """Test that overall flow."""

    with patch(
        "python_awair.AwairClient.query", side_effect=[USER_FIXTURE, DEVICES_FIXTURE]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONFIG
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "foo@bar.com (32406)"
        assert result["data"][CONF_ACCESS_TOKEN] == CONFIG[CONF_ACCESS_TOKEN]
        assert result["result"].unique_id == CONFIG_ENTRY_UNIQUE_ID
