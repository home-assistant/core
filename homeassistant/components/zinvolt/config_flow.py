"""Config flow for the Zinvolt integration."""

from collections.abc import Mapping
import logging
from typing import Any, override

import probatio
from zinvolt import ZinvoltClient
from zinvolt.exceptions import ZinvoltAuthenticationError, ZinvoltError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class ZinvoltConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Zinvolt."""

    async def _async_login(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> str | None:
        """Log in and set the unique ID, returning the token or None on error."""
        client = ZinvoltClient(session=async_get_clientsession(self.hass))
        try:
            token = await client.login(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            user_id = client.get_user_id()
        except ZinvoltAuthenticationError:
            errors["base"] = "invalid_auth"
        except ZinvoltError:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_id)
            return token
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            token := await self._async_login(user_input, errors)
        ):
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_EMAIL], data={CONF_ACCESS_TOKEN: token}
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None and (
            token := await self._async_login(user_input, errors)
        ):
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reauth_entry, data_updates={CONF_ACCESS_TOKEN: token}
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, {CONF_EMAIL: reauth_entry.title}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()
        if user_input is not None and (
            token := await self._async_login(user_input, errors)
        ):
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reconfigure_entry,
                title=user_input[CONF_EMAIL],
                data_updates={CONF_ACCESS_TOKEN: token},
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, {CONF_EMAIL: reconfigure_entry.title}
            ),
            errors=errors,
        )
