"""Test Discord config flow."""
from unittest.mock import patch

import discord

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.discord.const import DOMAIN
from homeassistant.const import CONF_SOURCE, CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import (
    CONF_CONFIG_FLOW,
    CONF_DATA,
    NAME,
    create_mocked_discord,
    mock_response,
    patch_discord_info,
)

from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.discord.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass: HomeAssistant):
    """Test user initialized flow."""
    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login"), patch_discord_info(
        mocked_discord
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA


async def test_flow_user_already_configured(hass: HomeAssistant):
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id="1234567890",
    )

    entry.add_to_hass(hass)

    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login"), patch_discord_info(
        mocked_discord
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid_Auth(hass: HomeAssistant):
    """Test user initialized flow with invalid token."""
    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login") as mock, patch_discord_info(mocked_discord):
        mock.side_effect = discord.LoginFailure
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "invalid_auth"}


async def test_flow_user_cannot_connect(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login") as mock, patch_discord_info(mocked_discord):
        mock.side_effect = discord.HTTPException(mock_response(), "")
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_unknown_error(hass: HomeAssistant):
    """Test user initialized flow with unreachable server."""
    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login") as mock, patch_discord_info(mocked_discord):
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "unknown"}


async def test_flow_import(hass: HomeAssistant):
    """Test an import flow."""
    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login"), patch_discord_info(
        mocked_discord
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF_CONFIG_FLOW,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"] == CONF_DATA


async def test_flow_import_already_configured(hass: HomeAssistant):
    """Test an import flow already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id="1234567890",
    )

    entry.add_to_hass(hass)

    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login"), patch_discord_info(
        mocked_discord
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=CONF_CONFIG_FLOW,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_flow_reauth(hass: HomeAssistant):
    """Test a reauth flow."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_CONFIG_FLOW,
        unique_id="1234567890",
    )

    entry.add_to_hass(hass)

    mocked_discord = await create_mocked_discord()
    with patch("discord.Client.login"), patch_discord_info(
        mocked_discord
    ), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                CONF_SOURCE: config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
                "unique_id": entry.unique_id,
            },
            data=CONF_CONFIG_FLOW,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "reauth_confirm"

        new_conf = {CONF_TOKEN: "1234567890"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=new_conf,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "reauth_successful"
        assert entry.data == {CONF_TOKEN: "1234567890"}
