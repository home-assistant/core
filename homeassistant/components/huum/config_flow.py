"""Config flow for huum integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from huum.exceptions import Forbidden, NotAuthenticated
from huum.huum import Huum
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HuumConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for huum."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_USERNAME: user_input[CONF_USERNAME]})
            try:
                huum = Huum(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                )
                await huum.status()
            except Forbidden, NotAuthenticated:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            huum = Huum(
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await huum.status()
            except Forbidden, NotAuthenticated:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unknown error")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            description_placeholders={
                "username": reauth_entry.data[CONF_USERNAME],
            },
            errors=errors,
        )
