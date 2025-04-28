"""Config flow for Rituals Perfume Genie integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
from pyrituals import Account, AuthenticationException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import ACCOUNT_HASH, DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class RitualsPerfumeGenieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rituals Perfume Genie."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        session = async_get_clientsession(self.hass)
        account = Account(user_input[CONF_EMAIL], user_input[CONF_PASSWORD], session)

        try:
            await account.authenticate()
        except ClientResponseError:
            _LOGGER.exception("Unexpected response")
            errors["base"] = "cannot_connect"
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(account.email)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=account.email,
                data={ACCOUNT_HASH: account.account_hash},
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
