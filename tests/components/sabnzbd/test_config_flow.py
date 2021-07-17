"""Define tests for the Sabnzbd config flow."""
from unittest.mock import patch

from pysabnzbd import SabnzbdApiException

from homeassistant import data_entry_flow
from homeassistant.components.sabnzbd import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
)

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_NAME: "Sabnzbd",
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_HOST: "localhost",
    CONF_PORT: 8080,
    CONF_PATH: "",
    CONF_SSL: False,
}


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Sabnzbd"
        assert result["data"][CONF_NAME] == "Sabnzbd"
        assert result["data"][CONF_API_KEY] == "edc3eee7330e4fdda04489e3fbc283d0"
        assert result["data"][CONF_HOST] == "localhost"
        assert result["data"][CONF_PORT] == 8080
        assert result["data"][CONF_PATH] == ""
        assert result["data"][CONF_SSL] is False


async def test_auth_error(hass):
    """Test that the user step fails."""
    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        side_effect=SabnzbdApiException("Some error"),
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
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        MockConfigEntry(
            domain=DOMAIN,
            unique_id="123456",
            data=VALID_CONFIG,
        ).add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == "abort"
        assert result["reason"] == "single_instance_allowed"
