"""Define tests for the Sabnzbd config flow."""
from unittest.mock import patch

from pysabnzbd import SabnzbdApiException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.sabnzbd import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_NAME,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_URL,
)
from homeassistant.data_entry_flow import FlowResultType

VALID_CONFIG = {
    CONF_NAME: "Sabnzbd",
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_URL: "http://localhost:8080",
    CONF_PATH: "",
}

VALID_CONFIG_OLD = {
    CONF_NAME: "Sabnzbd",
    CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
    CONF_HOST: "localhost",
    CONF_PORT: 8080,
    CONF_PATH: "",
    CONF_SSL: False,
}


async def test_create_entry(hass):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ), patch(
        "homeassistant.components.sabnzbd.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            VALID_CONFIG,
        )
        await hass.async_block_till_done()

        assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result2["title"] == "edc3eee7330e"
        assert result2["data"] == {
            CONF_API_KEY: "edc3eee7330e4fdda04489e3fbc283d0",
            CONF_NAME: "Sabnzbd",
            CONF_PATH: "",
            CONF_URL: "http://localhost:8080",
        }
        assert len(mock_setup_entry.mock_calls) == 1


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


async def test_import_flow(hass) -> None:
    """Test the import configuration flow."""
    with patch(
        "homeassistant.components.sabnzbd.sab.SabnzbdApi.check_available",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=VALID_CONFIG_OLD,
        )

        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "edc3eee7330e"
        assert result["data"][CONF_NAME] == "Sabnzbd"
        assert result["data"][CONF_API_KEY] == "edc3eee7330e4fdda04489e3fbc283d0"
        assert result["data"][CONF_HOST] == "localhost"
        assert result["data"][CONF_PORT] == 8080
        assert result["data"][CONF_PATH] == ""
        assert result["data"][CONF_SSL] is False
