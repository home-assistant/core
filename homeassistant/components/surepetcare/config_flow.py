"""Config flow for Sure Petcare integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import surepy
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, SURE_API_TIMEOUT

_LOGGER = logging.getLogger(__name__)

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class SurePetCareConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sure Petcare."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            client = surepy.Surepy(
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                auth_token=None,
                api_timeout=SURE_API_TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
            try:
                token = await client.sac.get_token()
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title="Sure Petcare",
                    data={**user_input, CONF_TOKEN: token},
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            client = surepy.Surepy(
                reauth_entry.data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                auth_token=None,
                api_timeout=SURE_API_TIMEOUT,
                session=async_get_clientsession(self.hass),
            )
            try:
                token = await client.sac.get_token()
            except SurePetcareAuthenticationError:
                errors["base"] = "invalid_auth"
            except SurePetcareError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_TOKEN: token,
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
