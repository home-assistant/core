"""Test the Minecraft Server config flow."""

from unittest.mock import patch

from homeassistant.components.minecraft_server.const import (
    CONF_UPDATE_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_UPDATE_INTERVAL_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS,
}

USER_INPUT_SAME_NAME = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "2.2.2.2",
    CONF_PORT: DEFAULT_PORT,
    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS,
}

USER_INPUT_INTERVAL_SMALL = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_UPDATE_INTERVAL: 4,
}

USER_INPUT_INTERVAL_LARGE = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: DEFAULT_PORT,
    CONF_UPDATE_INTERVAL: 86401,
}

USER_INPUT_PORT_SMALL = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 1023,
    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS,
}

USER_INPUT_PORT_LARGE = {
    CONF_NAME: DEFAULT_NAME,
    CONF_HOST: "1.1.1.1",
    CONF_PORT: 65536,
    CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL_SECONDS,
}


async def test_show_config_form(hass):
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_same_host(hass):
    """Test abort in case of same host name."""
    unique_id = f"{USER_INPUT[CONF_HOST].lower()}-{USER_INPUT[CONF_PORT]}"
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN, unique_id=unique_id, data=USER_INPUT
    )
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_update_interval_too_small(hass):
    """Test error in case of a too small update interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_INTERVAL_SMALL
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_update_interval"}


async def test_update_interval_too_large(hass):
    """Test error in case of a too large update interval."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_INTERVAL_LARGE
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_update_interval"}


async def test_port_too_small(hass):
    """Test error in case of a too small port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_SMALL
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_port_too_large(hass):
    """Test error in case of a too large port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT_PORT_LARGE
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_port"}


async def test_connection_failed(hass):
    """Test error in case of a failed connection."""
    with patch(
        "homeassistant.components.minecraft_server.MinecraftServer.async_check_connection"
    ):
        with patch(
            "homeassistant.components.minecraft_server.MinecraftServer.online",
            return_value=False,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
            )

            assert result["type"] == RESULT_TYPE_FORM
            assert result["errors"] == {"base": "cannot_connect"}


async def test_connection_succeeded(hass):
    """Test config entry in case of a successful connection."""
    with patch(
        "homeassistant.components.minecraft_server.MinecraftServer.async_check_connection"
    ):
        with patch(
            "homeassistant.components.minecraft_server.MinecraftServer.online",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_USER}, data=USER_INPUT
            )

            assert result["type"] == RESULT_TYPE_CREATE_ENTRY
            assert result["title"] == f"{USER_INPUT[CONF_HOST]}:{USER_INPUT[CONF_PORT]}"
            assert result["data"][CONF_NAME] == USER_INPUT[CONF_NAME]
            assert result["data"][CONF_HOST] == USER_INPUT[CONF_HOST]
            assert result["data"][CONF_PORT] == USER_INPUT[CONF_PORT]
            assert (
                result["data"][CONF_UPDATE_INTERVAL] == USER_INPUT[CONF_UPDATE_INTERVAL]
            )
