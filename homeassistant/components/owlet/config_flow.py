"""Config flow for Owlet Smart Sock integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from pyowletapi.api import OwletAPI
from pyowletapi.exceptions import (
    OwletCredentialsError,
    OwletDevicesError,
    OwletEmailError,
    OwletPasswordError,
)
from pyowletapi.sock import Sock
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_OWLET_EXPIRY, CONF_OWLET_REFRESH, DOMAIN, POLLING_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("region"): vol.In(["europe", "world"]),
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class OwletConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Owlet Smart Sock."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise config flow."""
        self._entry: ConfigEntry
        self._region: str
        self._username: str
        self._password: str
        self._devices: dict[str, Sock]
        self.reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._region = user_input[CONF_REGION]
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            owlet_api = OwletAPI(
                region=self._region,
                user=self._username,
                password=self._password,
                session=async_get_clientsession(self.hass),
            )

            await self.async_set_unique_id(self._username.lower())
            self._abort_if_unique_id_configured()

            try:
                token = await owlet_api.authenticate()
                await owlet_api.validate_authentication()

            except OwletDevicesError:
                errors["base"] = "no_devices"
            except OwletEmailError:
                errors["base"] = "invalid_email"
            except OwletPasswordError:
                errors["base"] = "invalid_password"
            except OwletCredentialsError:
                errors["base"] = "invalid_credentials"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=self._username,
                    data={
                        CONF_REGION: self._region,
                        CONF_USERNAME: self._username,
                        CONF_API_TOKEN: token[CONF_API_TOKEN],
                        CONF_OWLET_EXPIRY: token[CONF_OWLET_EXPIRY],
                        CONF_OWLET_REFRESH: token[CONF_OWLET_REFRESH],
                    },
                    options={CONF_SCAN_INTERVAL: POLLING_INTERVAL},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_reauth(self, user_input: Mapping[str, Any]) -> FlowResult:
        """Handle reauth."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        assert self.reauth_entry is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            entry_data = self.reauth_entry.data
            owlet_api = OwletAPI(
                entry_data[CONF_REGION],
                entry_data[CONF_USERNAME],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                token = await owlet_api.authenticate()
                if token:
                    self.hass.config_entries.async_update_entry(
                        self.reauth_entry, data={**entry_data, **token}
                    )

                await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)

                return self.async_abort(reason="reauth_successful")

            except OwletPasswordError:
                errors["base"] = "invalid_password"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error reauthenticating")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a options flow for owlet."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialise options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
