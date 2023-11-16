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
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION): vol.In(["europe", "world"]),
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class OwletConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Owlet Smart Sock."""

    VERSION = 1
    reauth_entry: ConfigEntry | None = None

    def __init__(self) -> None:
        """Initialise config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            owlet_api = OwletAPI(
                region=user_input[CONF_REGION],
                user=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )

            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            try:
                token = await owlet_api.authenticate()
                await owlet_api.validate_authentication()

            except OwletDevicesError:
                errors["base"] = "no_devices"
            except OwletEmailError:
                errors[CONF_USERNAME] = "invalid_email"
            except OwletPasswordError:
                errors[CONF_PASSWORD] = "invalid_password"
            except OwletCredentialsError:
                errors["base"] = "invalid_credentials"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data={
                        CONF_REGION: user_input[CONF_REGION],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        **token,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

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
                errors[CONF_PASSWORD] = "invalid_password"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error reauthenticating")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
