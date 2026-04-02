"""Config flow for the Duco integration."""

from __future__ import annotations

from typing import Any

from duco import DucoClient
from duco.exceptions import DucoConnectionError, DucoError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class DucoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Duco."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client = DucoClient(
                session=async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
            )
            try:
                board_info = await client.async_get_board_info()
                lan_info = await client.async_get_lan_info()
            except DucoConnectionError, DucoError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(lan_info.mac)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=board_info.box_name,
                    data={CONF_HOST: user_input[CONF_HOST]},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )
