"""Config flow for pvpc_hourly_pricing."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiopvpc import DEFAULT_POWER_KW, PVPCData
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import dt as dt_util

from .const import (
    ATTR_POWER,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    CONF_USE_API_TOKEN,
    DEFAULT_NAME,
    DEFAULT_TARIFF,
    DOMAIN,
    VALID_POWER,
    VALID_TARIFF,
)

_MAIL_TO_LINK = (
    "[consultasios@ree.es]"
    "(mailto:consultasios@ree.es?subject=Personal%20token%20request)"
)


class TariffSelectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for `pvpc_hourly_pricing`."""

    VERSION = 1
    _name: str | None = None
    _tariff: str | None = None
    _power: float | None = None
    _power_p3: float | None = None
    _use_api_token: bool = False
    _api_token: str | None = None
    _api: PVPCData | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PVPCOptionsFlowHandler:
        """Get the options flow for this handler."""
        return PVPCOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_TARIFF])
            self._abort_if_unique_id_configured()
            if not user_input[CONF_USE_API_TOKEN]:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        ATTR_TARIFF: user_input[ATTR_TARIFF],
                        ATTR_POWER: user_input[ATTR_POWER],
                        ATTR_POWER_P3: user_input[ATTR_POWER_P3],
                        CONF_API_TOKEN: None,
                    },
                )

            self._name = user_input[CONF_NAME]
            self._tariff = user_input[ATTR_TARIFF]
            self._power = user_input[ATTR_POWER]
            self._power_p3 = user_input[ATTR_POWER_P3]
            self._use_api_token = user_input[CONF_USE_API_TOKEN]
            return await self.async_step_api_token()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(ATTR_TARIFF, default=DEFAULT_TARIFF): VALID_TARIFF,
                vol.Required(ATTR_POWER, default=DEFAULT_POWER_KW): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=DEFAULT_POWER_KW): VALID_POWER,
                vol.Required(CONF_USE_API_TOKEN, default=False): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_api_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle optional step to define API token for extra sensors."""
        if user_input is not None:
            self._api_token = user_input[CONF_API_TOKEN]
            return await self._async_verify(
                "api_token",
                data_schema=vol.Schema(
                    {vol.Required(CONF_API_TOKEN, default=self._api_token): str}
                ),
            )
        return self.async_show_form(
            step_id="api_token",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_TOKEN, default=self._api_token): str}
            ),
            description_placeholders={"mail_to_link": _MAIL_TO_LINK},
        )

    async def _async_verify(
        self, step_id: str, data_schema: vol.Schema
    ) -> ConfigFlowResult:
        """Attempt to verify the provided configuration."""
        errors: dict[str, str] = {}
        auth_ok = True
        if self._use_api_token:
            if not self._api:
                self._api = PVPCData(session=async_get_clientsession(self.hass))
            auth_ok = await self._api.check_api_token(dt_util.utcnow(), self._api_token)
        if not auth_ok:
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id=step_id,
                data_schema=data_schema,
                errors=errors,
                description_placeholders={"mail_to_link": _MAIL_TO_LINK},
            )

        data = {
            CONF_NAME: self._name,
            ATTR_TARIFF: self._tariff,
            ATTR_POWER: self._power,
            ATTR_POWER_P3: self._power_p3,
            CONF_API_TOKEN: self._api_token if self._use_api_token else None,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )

        assert self._name is not None
        return self.async_create_entry(title=self._name, data=data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication with ESIOS Token."""
        self._api_token = entry_data.get(CONF_API_TOKEN)
        self._use_api_token = self._api_token is not None
        self._name = entry_data[CONF_NAME]
        self._tariff = entry_data[ATTR_TARIFF]
        self._power = entry_data[ATTR_POWER]
        self._power_p3 = entry_data[ATTR_POWER_P3]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        data_schema = vol.Schema(
            {
                vol.Required(CONF_USE_API_TOKEN, default=self._use_api_token): bool,
                vol.Optional(CONF_API_TOKEN, default=self._api_token): str,
            }
        )
        if user_input:
            self._api_token = user_input[CONF_API_TOKEN]
            self._use_api_token = user_input[CONF_USE_API_TOKEN]
            return await self._async_verify("reauth_confirm", data_schema)
        return self.async_show_form(step_id="reauth_confirm", data_schema=data_schema)


class PVPCOptionsFlowHandler(OptionsFlow):
    """Handle PVPC options."""

    _power: float | None = None
    _power_p3: float | None = None

    async def async_step_api_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle optional step to define API token for extra sensors."""
        if user_input is not None and user_input.get(CONF_API_TOKEN):
            return self.async_create_entry(
                title="",
                data={
                    ATTR_POWER: self._power,
                    ATTR_POWER_P3: self._power_p3,
                    CONF_API_TOKEN: user_input[CONF_API_TOKEN],
                },
            )

        # Fill options with entry data
        api_token = self.config_entry.options.get(
            CONF_API_TOKEN, self.config_entry.data.get(CONF_API_TOKEN)
        )
        return self.async_show_form(
            step_id="api_token",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_TOKEN, default=api_token): str}
            ),
            description_placeholders={"mail_to_link": _MAIL_TO_LINK},
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            if user_input[CONF_USE_API_TOKEN]:
                self._power = user_input[ATTR_POWER]
                self._power_p3 = user_input[ATTR_POWER_P3]
                return await self.async_step_api_token(user_input)
            return self.async_create_entry(
                title="",
                data={
                    ATTR_POWER: user_input[ATTR_POWER],
                    ATTR_POWER_P3: user_input[ATTR_POWER_P3],
                    CONF_API_TOKEN: None,
                },
            )

        # Fill options with entry data
        options = self.config_entry.options
        data = self.config_entry.data
        power = options.get(ATTR_POWER, data[ATTR_POWER])
        power_valley = options.get(ATTR_POWER_P3, data[ATTR_POWER_P3])
        api_token = options.get(CONF_API_TOKEN, data.get(CONF_API_TOKEN))
        use_api_token = api_token is not None
        schema = vol.Schema(
            {
                vol.Required(ATTR_POWER, default=power): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=power_valley): VALID_POWER,
                vol.Required(CONF_USE_API_TOKEN, default=use_api_token): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
