"""Config flow for Read Your Meter Pro integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyrympro import CannotConnectError, RymPro, UnauthorizedError
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, CONF_TOKEN, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    rympro = RymPro(async_get_clientsession(hass))

    token = await rympro.login(data[CONF_EMAIL], data[CONF_PASSWORD], "ha")

    info = await rympro.account_info()

    return {CONF_TOKEN: token, CONF_UNIQUE_ID: info["accountNumber"]}


class RymproConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Read Your Meter Pro."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnectError:
            errors["base"] = "cannot_connect"
        except UnauthorizedError:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            title = user_input[CONF_EMAIL]
            data = {**user_input, **info}

            if self.source != SOURCE_REAUTH:
                await self.async_set_unique_id(info[CONF_UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=data)

            return self.async_update_reload_and_abort(
                self._get_reauth_entry(),
                title=title,
                data=data,
                unique_id=info[CONF_UNIQUE_ID],
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_user()
