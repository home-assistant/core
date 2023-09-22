"""Tests for the Minecraft Server config flow."""

from unittest.mock import patch

from mcstatus import JavaServer

from homeassistant.components.minecraft_server.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_ADDRESS, TEST_HOST, TEST_JAVA_STATUS_RESPONSE, TEST_PORT

USER_INPUT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_ADDRESS: TEST_ADDRESS,
}


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_lookup_failed(hass: HomeAssistant) -> None:
    """Test error in case of a failed connection."""
    with patch(
        "mcstatus.server.JavaServer.async_lookup",
        side_effect=ValueError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_failed(hass: HomeAssistant) -> None:
    """Test error in case of a failed connection."""
    with patch(
        "mcstatus.server.JavaServer.async_lookup",
        return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
    ), patch("mcstatus.server.JavaServer.async_status", side_effect=OSError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_succeeded(hass: HomeAssistant) -> None:
    """Test config entry in case of a successful connection with a host name."""
    with patch(
        "mcstatus.server.JavaServer.async_lookup",
        return_value=JavaServer(host=TEST_HOST, port=TEST_PORT),
    ), patch(
        "mcstatus.server.JavaServer.async_status",
        return_value=TEST_JAVA_STATUS_RESPONSE,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == USER_INPUT[CONF_ADDRESS]
        assert result["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
        assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
