"""Config flow for Rituals Perfume Genie integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import ClientResponseError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, USERNAME, PASSWORD, ACCOUNT_HASH
from pyrituals import Account, AuthenticationException

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


# Subclass of HA ConfigFlow + version bump for V2
class RitualsPerfumeGenieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rituals Perfume Genie."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
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

            # In V2 we store email + password instead of account_hash
            return self.async_create_entry(
                title=account.email,
                data={USERNAME: user_input[CONF_EMAIL], PASSWORD: user_input[CONF_PASSWORD]},
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    # Simple reauth flow to retrieve credentials again (V2)
    async def async_step_reauth(self, data: dict[str, Any]) -> FlowResult:
        """Reauth step: request credentials again for V2 token."""
        # Keep it simple and compatible with the existing flow
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Form to log in again (V2)."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=DATA_SCHEMA,
            )

        session = async_get_clientsession(self.hass)
        account = Account(user_input[CONF_EMAIL], user_input[CONF_PASSWORD], session)

        errors = {}
        try:
            await account.authenticate()
        except ClientResponseError:
            _LOGGER.exception("Unexpected response (reauth)")
            errors["base"] = "cannot_connect"
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception (reauth)")
            errors["base"] = "unknown"
        else:
            # Find the entry with the same unique_id and update stored data
            entries = self.hass.config_entries.async_entries(DOMAIN)
            for entry in entries:
                if entry.unique_id == account.email:
                    new_data = dict(entry.data)
                    new_data[USERNAME] = user_input[CONF_EMAIL]
                    new_data[PASSWORD] = user_input[CONF_PASSWORD]
                    new_data.pop(ACCOUNT_HASH, None)  # remove old field
                    self.hass.config_entries.async_update_entry(entry, data=new_data)
                    await self.hass.config_entries.async_reload(entry.entry_id)
                    break

            return self.async_abort(reason="reauth_success")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )
