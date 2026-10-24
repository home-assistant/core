"""Config flow for the FENIX Control integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pyfenixcontrol import (
    FenixControlAuthError,
    FenixControlClient,
    FenixControlError,
    PasswordAuth,
)

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class FenixControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FENIX Control."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_get_user_id(
        self, email: str, password: str
    ) -> tuple[str | None, dict[str, str]]:
        """Log in and return the account ID, or the form errors."""
        # A dedicated session keeps the login cookies apart; it shares Home
        # Assistant's connector, so it is detached instead of closed
        session = async_create_clientsession(self.hass, auto_cleanup=False)
        client = FenixControlClient(PasswordAuth(session, email, password))
        try:
            return await client.get_user_id(), {}
        except FenixControlAuthError:
            return None, {"base": "invalid_auth"}
        except FenixControlError:
            return None, {"base": "cannot_connect"}
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected exception")
            return None, {"base": "unknown"}
        finally:
            session.detach()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, errors = await self._async_get_user_id(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if user_id:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a rejected login."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the e-mail address and the new password."""
        reauth_entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            user_id, errors = await self._async_get_user_id(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if user_id:
                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_EMAIL: (user_input or reauth_entry.data)[CONF_EMAIL]},
            ),
            errors=errors,
        )
