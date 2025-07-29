"""Config flow for the AirPatrol integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from airpatrol.api import AirPatrolAPI, AirPatrolAuthenticationError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import AbortFlow
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AirPatrolConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AirPatrol."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                # Test the connection before creating the entry
                session = async_get_clientsession(self.hass)

                api = await AirPatrolAPI.authenticate(
                    session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
                # Store the access token in the config entry
                user_input["access_token"] = api.get_access_token()
                await self.async_set_unique_id(api.get_unique_id())
                self._abort_if_unique_id_configured()

            except AirPatrolAuthenticationError:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                # Re-raise AbortFlow exceptions (like already_configured)
                raise
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=DOMAIN, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication with new credentials."""
        errors: dict[str, str] = {}
        entry = self.context.get("entry")
        if user_input is not None:
            try:
                session = async_get_clientsession(self.hass)
                api = await AirPatrolAPI.authenticate(
                    session, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )

                if isinstance(entry, ConfigEntry):
                    self.hass.config_entries.async_update_entry(
                        entry,
                        data={
                            **entry.data,
                            CONF_EMAIL: user_input[CONF_EMAIL],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            "access_token": api.get_access_token(),
                        },
                    )
                    await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")
            except AirPatrolAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        # Show the form (pre-fill with existing email if available)
        email = ""

        if isinstance(entry, ConfigEntry):
            email = entry.data.get(CONF_EMAIL, "")
        return self.async_show_form(
            step_id="reauth",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"email": email},
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
