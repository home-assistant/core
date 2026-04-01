"""Config flow for the Chess.com integration."""

from __future__ import annotations

import logging
from typing import Any

from chess_com_api import ChessComClient, NotFoundError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ChessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Chess.com."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = ChessComClient(session=session)
            try:
                user = await client.get_player(user_input[CONF_USERNAME])
                await client.get_player_stats(user_input[CONF_USERNAME])
            except NotFoundError:
                errors["base"] = "player_not_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(str(user.player_id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user.name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_USERNAME): str}),
            errors=errors,
        )
