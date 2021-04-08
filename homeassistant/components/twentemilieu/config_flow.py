"""Config flow to configure the Twente Milieu integration."""
from __future__ import annotations

from typing import Any

from twentemilieu import (
    TwenteMilieu,
    TwenteMilieuAddressError,
    TwenteMilieuConnectionError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_ID
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_HOUSE_LETTER, CONF_HOUSE_NUMBER, CONF_POST_CODE, DOMAIN


class TwenteMilieuFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Twente Milieu config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def _show_setup_form(
        self, errors: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POST_CODE): str,
                    vol.Required(CONF_HOUSE_NUMBER): str,
                    vol.Optional(CONF_HOUSE_LETTER): str,
                }
            ),
            errors=errors or {},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle a flow initiated by the user."""
        if user_input is None:
            return await self._show_setup_form(user_input)

        errors = {}

        session = async_get_clientsession(self.hass)

        twentemilieu = TwenteMilieu(
            post_code=user_input[CONF_POST_CODE],
            house_number=user_input[CONF_HOUSE_NUMBER],
            house_letter=user_input.get(CONF_HOUSE_LETTER),
            session=session,
        )

        try:
            unique_id = await twentemilieu.unique_id()
        except TwenteMilieuConnectionError:
            errors["base"] = "cannot_connect"
            return await self._show_setup_form(errors)
        except TwenteMilieuAddressError:
            errors["base"] = "invalid_address"
            return await self._show_setup_form(errors)

        entries = self._async_current_entries()
        for entry in entries:
            if entry.data[CONF_ID] == unique_id:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=str(unique_id),
            data={
                CONF_ID: unique_id,
                CONF_POST_CODE: user_input[CONF_POST_CODE],
                CONF_HOUSE_NUMBER: user_input[CONF_HOUSE_NUMBER],
                CONF_HOUSE_LETTER: user_input.get(CONF_HOUSE_LETTER),
            },
        )
