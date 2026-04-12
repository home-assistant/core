"""Config Flow for the Aquarite integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from aioaquarite import AquariteAuth, AquariteClient, AuthenticationError

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL, DOMAIN

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class AquariteOptionsFlow(OptionsFlow):
    """Options flow for Aquarite."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options form."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current = self.config_entry.options.get(
            CONF_HEALTH_CHECK_INTERVAL, DEFAULT_HEALTH_CHECK_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HEALTH_CHECK_INTERVAL, default=current
                ): vol.All(int, vol.Range(min=60, max=3600)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


class AquariteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Aquarite config flow."""

    @staticmethod
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AquariteOptionsFlow:
        """Return the options flow handler."""
        return AquariteOptionsFlow()

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._user_data: dict[str, Any] = {}
        self._available_pools: dict[str, str] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is not None:
            self._user_data = {
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            }
            return await self.async_step_pool()

        return self.async_show_form(step_id="user", data_schema=AUTH_SCHEMA)

    async def async_step_pool(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the pool selection step."""
        if user_input is not None:
            pool_id: str = user_input["pool_id"]

            await self.async_set_unique_id(pool_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self._available_pools.get(pool_id, pool_id),
                data={
                    CONF_USERNAME: self._user_data[CONF_USERNAME],
                    CONF_PASSWORD: self._user_data[CONF_PASSWORD],
                    "pool_id": pool_id,
                },
            )

        try:
            session = async_get_clientsession(self.hass)
            auth = AquariteAuth(
                session,
                self._user_data[CONF_USERNAME],
                self._user_data[CONF_PASSWORD],
            )
            await auth.authenticate()
            api = AquariteClient(auth)
            self._available_pools = await api.get_pools()
        except AuthenticationError:
            return self.async_show_form(
                step_id="user",
                data_schema=AUTH_SCHEMA,
                errors={"base": "auth_error"},
            )
        except Exception:
            return self.async_show_form(
                step_id="user",
                data_schema=AUTH_SCHEMA,
                errors={"base": "unknown_error"},
            )

        if not self._available_pools:
            return self.async_show_form(
                step_id="user",
                data_schema=AUTH_SCHEMA,
                errors={"base": "no_pools_found"},
            )

        pool_schema = vol.Schema(
            {vol.Required("pool_id"): vol.In(self._available_pools)}
        )
        return self.async_show_form(step_id="pool", data_schema=pool_schema)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauth flow."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth credential input."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                auth = AquariteAuth(
                    session,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "auth_error"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=reauth_entry.data.get(CONF_USERNAME, ""),
                ): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=schema, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            try:
                auth = AquariteAuth(
                    session,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
                await auth.authenticate()
            except AuthenticationError:
                errors["base"] = "auth_error"
            else:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        **reconfigure_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_USERNAME,
                    default=reconfigure_entry.data.get(CONF_USERNAME, ""),
                ): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
            }
        )
        return self.async_show_form(
            step_id="reconfigure", data_schema=schema, errors=errors
        )
