"""Config flow for the Ridder HortiMaX Pro (HortOS) integration."""

from collections.abc import Mapping
from typing import Any, override

from aiohortos import (
    DEFAULT_BASE_URL,
    HortosAuthenticationError,
    HortosClient,
    HortosError,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BASE_URL, DOMAIN, LOGGER

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): str,
    }
)

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class HortimaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ridder HortiMaX Pro."""

    async def _async_validate(
        self, api_key: str, base_url: str, errors: dict[str, str]
    ) -> str | None:
        """Authenticate and list controllers, returning the organisation id."""
        client = HortosClient(
            api_key,
            session=async_get_clientsession(self.hass),
            base_url=base_url,
        )
        try:
            tokens = await client.authenticate()
            devices = await client.get_device_names()
        except HortosAuthenticationError:
            errors["base"] = "invalid_auth"
        except HortosError:
            errors["base"] = "cannot_connect"
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unexpected error validating the HortOS API")
            errors["base"] = "unknown"
        else:
            if not devices:
                errors["base"] = "no_devices"
            elif tokens.organisation is not None:
                return tokens.organisation.id
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            organisation_id = await self._async_validate(
                user_input[CONF_API_KEY], user_input[CONF_BASE_URL], errors
            )
            if not errors:
                if organisation_id is not None:
                    await self.async_set_unique_id(organisation_id)
                    self._abort_if_unique_id_configured()
                else:
                    # An API that does not report an organisation leaves us
                    # without a stable id; fall back to rejecting an exact
                    # duplicate of an existing entry.
                    self._async_abort_entries_match(user_input)
                return self.async_create_entry(
                    title="Ridder HortiMaX Pro", data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a re-authentication flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            organisation_id = await self._async_validate(
                user_input[CONF_API_KEY],
                reauth_entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
                errors,
            )
            if not errors:
                # A valid key for a *different* organisation would silently
                # repoint this entry at another account, keeping the entities
                # and history of the old one.
                if organisation_id is not None:
                    await self.async_set_unique_id(organisation_id)
                    self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors
        )
