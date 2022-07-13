"""Test the Discord Calendar config flow."""
from unittest.mock import patch

import nextcord

from homeassistant import config_entries
from homeassistant.components.discal.config_flow import ValueError
from homeassistant.components.discal.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_login_failure(hass: HomeAssistant) -> None:
    """Test we handle invalid tokens."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.discal.config_flow.validate_input",
        side_effect=nextcord.LoginFailure,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "token": "thisisatotallyavalidtokendefinitelynotsarcasm",
                "guild_ids": "0,20234567,3098765,41234567,5863450987,612094816,709183,8129,901238",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_token"}


async def test_form_malformed_guilds(hass: HomeAssistant) -> None:
    """Test a string with letters in it fails with :py:class:`ValueError`."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.discal.config_flow.validate_input",
        side_effect=ValueError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "token": "thisisatotallyavalidtokendefinitelynotsarcasm",
                "guild_ids": "a1bc,2def,ghi3",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "malformed_guilds"}
