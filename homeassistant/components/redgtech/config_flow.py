"""Config flow for the Redgtech integration."""

from __future__ import annotations

import logging
from typing import Any

from redgtech_api.api import RedgtechAPI, RedgtechAuthError, RedgtechConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RedgtechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow for Redgtech integration."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial user step for login."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            api: Any = RedgtechAPI()  # type: ignore[no-untyped-call]
            try:
                await api.login(email, password)
            except RedgtechAuthError:
                errors["base"] = "invalid_auth"
            except RedgtechConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during login")
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Login successful, token received")
                return self.async_create_entry(
                    title=email,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle re-authentication request from Redgtech."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            email = reauth_entry.data[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]

            api: Any = RedgtechAPI()  # type: ignore[no-untyped-call]
            try:
                await api.login(email, password)
            except RedgtechAuthError:
                errors["base"] = "invalid_auth"
            except RedgtechConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error during reauthentication")
                errors["base"] = "unknown"
            else:
                _LOGGER.debug("Reauthentication successful")
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )
