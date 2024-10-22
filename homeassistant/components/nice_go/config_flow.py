"""Config flow for Nice G.O. integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from nice_go import AuthFailedError, NiceGOApi
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_REFRESH_TOKEN, CONF_REFRESH_TOKEN_CREATION_TIME, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class NiceGOConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nice G.O."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()

            hub = NiceGOApi()

            try:
                refresh_token = await hub.authenticate(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        errors = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            hub = NiceGOApi()

            try:
                refresh_token = await hub.authenticate(
                    user_input[CONF_EMAIL],
                    user_input[CONF_PASSWORD],
                    async_get_clientsession(self.hass),
                )
            except AuthFailedError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **user_input,
                        CONF_REFRESH_TOKEN: refresh_token,
                        CONF_REFRESH_TOKEN_CREATION_TIME: datetime.now().timestamp(),
                    },
                    unique_id=user_input[CONF_EMAIL],
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            ),
            description_placeholders={CONF_NAME: reauth_entry.title},
            errors=errors,
        )
