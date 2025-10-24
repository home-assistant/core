"""Config flow for Rituals Perfume Genie integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, cast

from aiohttp import ClientResponseError
from pyrituals import Account, AuthenticationException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, PASSWORD, USERNAME

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

PASSWORD_ONLY_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


# Subclass of HA ConfigFlow + version bump for V2
class RitualsPerfumeGenieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rituals Perfume Genie."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        _LOGGER.debug("CF:user form opened")

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        errors = {}

        session = async_create_clientsession(self.hass)
        account = Account(
            cast(str, user_input[CONF_EMAIL]),
            cast(str, user_input[CONF_PASSWORD]),
            session,
        )

        try:
            await account.authenticate()
        except ClientResponseError:
            errors["base"] = "cannot_connect"
        except AuthenticationException:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("CF:user unexpected exception")
            errors["base"] = "unknown"
        else:
            _LOGGER.debug("CF:user authenticate OK for %s", account.email)
            await self.async_set_unique_id(account.email)
            self._abort_if_unique_id_configured()
            _LOGGER.debug("CF:user creating entry for %s", account.email)
            return self.async_create_entry(
                title=account.email,
                data={
                    USERNAME: user_input[CONF_EMAIL],
                    PASSWORD: user_input[CONF_PASSWORD],
                },
            )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    # Simple reauth flow to retrieve credentials again (V2)
    async def async_step_reauth(self, data: Mapping[str, Any]) -> ConfigFlowResult:
        """Reauth step: request credentials again for V2 token."""
        # Keep it simple and compatible with the existing flow
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Form to log in again (V2)."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=PASSWORD_ONLY_SCHEMA,
            )

        entry_id = self.context.get("entry_id")
        entry = self.hass.config_entries.async_get_entry(entry_id) if entry_id else None
        if entry is None:
            _LOGGER.exception("Reauth: entry not found from context")
            return self.async_abort(reason="unknown")

        email = cast(str, entry.unique_id or entry.data.get(USERNAME))
        session = async_create_clientsession(self.hass)
        account = Account(email, user_input[CONF_PASSWORD], session)

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
            new_data = dict(entry.data)
            new_data[USERNAME] = email
            new_data[PASSWORD] = user_input[CONF_PASSWORD]
            self.hass.config_entries.async_update_entry(entry, data=new_data)
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reauth_success")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=PASSWORD_ONLY_SCHEMA,
            errors=errors,
        )
