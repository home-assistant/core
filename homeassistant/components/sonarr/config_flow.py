"""Config flow for Sonarr."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from aiopyarr import ArrAuthenticationException, ArrException
from aiopyarr.models.host_configuration import PyArrHostConfiguration
from aiopyarr.sonarr_client import SonarrClient
import voluptuous as vol
import yarl

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_URL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_VERIFY_SSL,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_input(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    host_configuration = PyArrHostConfiguration(
        api_token=data[CONF_API_KEY],
        url=data[CONF_URL],
        verify_ssl=data[CONF_VERIFY_SSL],
    )

    sonarr = SonarrClient(
        host_configuration=host_configuration,
        session=async_get_clientsession(hass),
    )

    await sonarr.async_get_system_status()


class SonarrConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sonarr."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> SonarrOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SonarrOptionsFlowHandler()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle configuration by re-auth."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                description_placeholders={
                    "url": self._get_reauth_entry().data[CONF_URL]
                },
                errors={},
            )

        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # aiopyarr defaults to the service port if one isn't given
            # this is counter to standard practice where http = 80
            # and https = 443.
            if CONF_URL in user_input:
                url = yarl.URL(user_input[CONF_URL])
                user_input[CONF_URL] = f"{url.scheme}://{url.host}:{url.port}{url.path}"

            if self.source == SOURCE_REAUTH:
                user_input = {**self._get_reauth_entry().data, **user_input}

            if CONF_VERIFY_SSL not in user_input:
                user_input[CONF_VERIFY_SSL] = DEFAULT_VERIFY_SSL

            try:
                await _validate_input(self.hass, user_input)
            except ArrAuthenticationException:
                errors = {"base": "invalid_auth"}
            except ArrException:
                errors = {"base": "cannot_connect"}
            except Exception:
                _LOGGER.exception("Unexpected exception")
                return self.async_abort(reason="unknown")
            else:
                if self.source == SOURCE_REAUTH:
                    return self.async_update_reload_and_abort(
                        self._get_reauth_entry(), data=user_input
                    )

                parsed = yarl.URL(user_input[CONF_URL])

                return self.async_create_entry(
                    title=parsed.host or "Sonarr", data=user_input
                )

        data_schema = self._get_user_data_schema()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(data_schema),
            errors=errors,
        )

    def _get_user_data_schema(self) -> dict[vol.Marker, type]:
        """Get the data schema to display user form."""
        if self.source == SOURCE_REAUTH:
            return {vol.Required(CONF_API_KEY): str}

        data_schema: dict[vol.Marker, type] = {
            vol.Required(CONF_URL): str,
            vol.Required(CONF_API_KEY): str,
        }

        if self.show_advanced_options:
            data_schema[vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL)] = (
                bool
            )

        return data_schema


class SonarrOptionsFlowHandler(OptionsFlow):
    """Handle Sonarr client options."""

    async def async_step_init(
        self, user_input: dict[str, int] | None = None
    ) -> ConfigFlowResult:
        """Manage Sonarr options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_UPCOMING_DAYS,
                default=self.config_entry.options.get(
                    CONF_UPCOMING_DAYS, DEFAULT_UPCOMING_DAYS
                ),
            ): int,
            vol.Optional(
                CONF_WANTED_MAX_ITEMS,
                default=self.config_entry.options.get(
                    CONF_WANTED_MAX_ITEMS, DEFAULT_WANTED_MAX_ITEMS
                ),
            ): int,
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
