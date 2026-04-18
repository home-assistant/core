"""Config flow for the Lichess integration."""

from __future__ import annotations

import logging
from typing import Any

from aiolichess import AioLichess
from aiolichess.exceptions import AioLichessError, AuthError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class LichessConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Lichess."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = AioLichess(session=session)
            try:
                user = await client.get_all(token=user_input[CONF_API_TOKEN])
            except AuthError:
                errors["base"] = "invalid_auth"
            except AioLichessError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                username = user.username
                player_id = user.id
                await self.async_set_unique_id(player_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=username, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )
