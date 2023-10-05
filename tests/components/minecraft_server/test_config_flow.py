"""Tests for the Minecraft Server config flow."""

from unittest.mock import patch

from homeassistant.components.minecraft_server.api import (
    MinecraftServerAddressError,
    MinecraftServerType,
)
from homeassistant.components.minecraft_server.const import DEFAULT_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import TEST_ADDRESS

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


async def test_address_validation_failed(hass: HomeAssistant) -> None:
    """Test error in case of a failed connection."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=[MinecraftServerAddressError, MinecraftServerAddressError],
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_java_connection_failed(hass: HomeAssistant) -> None:
    """Test error in case of a failed connection to a Java Edition server."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=[MinecraftServerAddressError, None],
        return_value=None,
    ), patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_is_online",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_bedrock_connection_failed(hass: HomeAssistant) -> None:
    """Test error in case of a failed connection to a Bedrock Edition server."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=[None, MinecraftServerAddressError],
        return_value=None,
    ), patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_is_online",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_java_connection_succeeded(hass: HomeAssistant) -> None:
    """Test config entry in case of a successful connection to a Java Edition server."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=[
            MinecraftServerAddressError,  # async_step_user (Bedrock Edition)
            None,  # async_step_user (Java Edition)
            None,  # async_setup_entry
        ],
        return_value=None,
    ), patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_is_online",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == USER_INPUT[CONF_ADDRESS]
        assert result["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
        assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result["data"][CONF_TYPE] == MinecraftServerType.JAVA_EDITION


async def test_bedrock_connection_succeeded(hass: HomeAssistant) -> None:
    """Test config entry in case of a successful connection to a Bedrock Edition server."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=None,
        return_value=None,
    ), patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_is_online",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == USER_INPUT[CONF_ADDRESS]
        assert result["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
        assert result["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result["data"][CONF_TYPE] == MinecraftServerType.BEDROCK_EDITION


async def test_recovery(hass: HomeAssistant) -> None:
    """Test config flow recovery (successful connection after a failed connection)."""
    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=[MinecraftServerAddressError, MinecraftServerAddressError],
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.__init__",
        side_effect=None,
        return_value=None,
    ), patch(
        "homeassistant.components.minecraft_server.api.MinecraftServer.async_is_online",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            flow_id=result["flow_id"], user_input=USER_INPUT
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == USER_INPUT[CONF_ADDRESS]
        assert result2["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
        assert result2["data"][CONF_ADDRESS] == TEST_ADDRESS
        assert result2["data"][CONF_TYPE] == MinecraftServerType.BEDROCK_EDITION
