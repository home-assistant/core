"""Config flow for Discord Calendar integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import nextcord
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("token"): str,
        vol.Required("guild_ids"): str,
    }
)


async def verify_guilds(bot: nextcord.Client, guild_ids: list[int]) -> None:
    """Verify that the Guild IDs provided are the IDs of actual servers."""
    for guild_id in guild_ids:
        await bot.fetch_guild(guild_id)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user-provided token allows us to login."""

    if re.match(r"\d+(?:, *\d+)*,?", guild_ids := data["guild_ids"].strip()):
        data["guild_ids"] = [int(guild_id) for guild_id in guild_ids.split(",")]
    else:
        raise ValueError

    bot = nextcord.Client()
    await bot.login(data["token"])
    await verify_guilds(bot, data["guild_ids"])
    assert bot.user is not None
    data.update(bot_name=bot.user.name)
    await bot.close()
    return data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Discord Calendar."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        errors: dict[str, str] = {}

        try:
            data = await validate_input(self.hass, user_input)
        except ValueError:
            errors.update(base="malformed_guilds")
        except nextcord.LoginFailure:
            errors.update(base="invalid_token")
        except nextcord.NotFound:
            errors.update(base="server_not_found")
        except nextcord.HTTPException:
            errors.update(base="connection_error")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors.update(base="unknown")
        else:
            await self.async_set_unique_id(user_input["token"][0::2])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=data["bot_name"], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
