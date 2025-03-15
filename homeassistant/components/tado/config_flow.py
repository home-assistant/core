"""Config flow for Tado integration."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
import logging
from typing import Any

from PyTado.interface import Tado
import requests.exceptions
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service_info.zeroconf import (
    ATTR_PROPERTIES_ID,
    ZeroconfServiceInfo,
)

from .const import (
    CONF_FALLBACK,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_OPTIONS,
    DOMAIN,
    UNIQUE_ID,
)

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    try:
        tado = await hass.async_add_executor_job(Tado)
        tado_me = await hass.async_add_executor_job(tado.get_me)
    except KeyError as ex:
        raise InvalidAuth from ex
    except RuntimeError as ex:
        raise CannotConnect from ex
    except requests.exceptions.HTTPError as ex:
        if 400 <= ex.response.status_code < 500:
            raise InvalidAuth from ex
        raise CannotConnect from ex

    if "homes" not in tado_me or not tado_me["homes"]:
        raise NoHomes

    home = tado_me["homes"][0]
    return {"title": home["name"], UNIQUE_ID: str(home["id"])}


class TadoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tado."""

    VERSION = 1
    login_task: asyncio.Task | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    tado: Tado | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input:
            try:
                validated = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except NoHomes:
                errors["base"] = "no_homes"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                await self.async_set_unique_id(validated[UNIQUE_ID])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=validated["title"], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth on credential failure."""
        return await self.async_step_reauth_prepare()

    async def async_step_reauth_prepare(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prepare reauth."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_prepare")

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle users reauth credentials."""

        async def _wait_for_login() -> None:
            """Wait for the user to login."""
            _LOGGER.debug("Waiting for device activation")
            try:
                await self.hass.async_add_executor_job(self.tado.device_activation)
            except Exception as ex:
                _LOGGER.exception("Error while waiting for device activation")
                raise CannotConnect from ex

            if (
                await self.hass.async_add_executor_job(
                    self.tado.device_activation_status
                )
                != "COMPLETED"
            ):
                raise CannotConnect

            _LOGGER.debug("Device activation completed. Obtaining tokens")

        if self.tado is None:
            _LOGGER.debug("Initiating device activation")
            self.tado = await self.hass.async_add_executor_job(Tado)
            tado_device_url = await self.hass.async_add_executor_job(
                self.tado.device_verification_url
            )
            user_code = tado_device_url.split("user_code=")[-1]

        _LOGGER.debug("Checking login task")
        if self.login_task is None:
            _LOGGER.debug("Creating task for device activation")
            self.login_task = self.hass.async_create_task(_wait_for_login())

        if self.login_task.done():
            _LOGGER.debug("Login task is done, checking results")
            if self.login_task.exception():
                return self.async_show_progress_done(
                    next_step_id="could_not_authenticate"
                )
            self.access_token = await self.hass.async_add_executor_job(
                self.tado.get_access_token
            )
            self.refresh_token = await self.hass.async_add_executor_job(
                self.tado.get_refresh_token
            )
            return self.async_show_progress_done(next_step_id="finalize_reauth_login")

        return self.async_show_progress(
            step_id="reauth_confirm",
            progress_action="wait_for_device",
            description_placeholders={
                "url": tado_device_url,
                "code": user_code,
            },
            progress_task=self.login_task,
        )

    async def async_step_finalize_reauth_login(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the finalization of reauth."""
        return self.async_update_reload_and_abort(
            self._get_reauth_entry(),
            data={
                CONF_ACCESS_TOKEN: self.access_token,
                CONF_PASSWORD: self.refresh_token,
            },
        )

    async def async_step_could_not_authenticate(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle issues that need transition await from progress step."""
        return self.async_abort(reason="could_not_authenticate")

    async def async_step_homekit(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle HomeKit discovery."""
        self._async_abort_entries_match()
        properties = {
            key.lower(): value for key, value in discovery_info.properties.items()
        }
        await self.async_set_unique_id(properties[ATTR_PROPERTIES_ID])
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlow):
    """Handle an option flow for Tado."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""
        if user_input:
            return self.async_create_entry(data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_FALLBACK,
                    default=self.config_entry.options.get(
                        CONF_FALLBACK, CONST_OVERLAY_TADO_DEFAULT
                    ),
                ): vol.In(CONST_OVERLAY_TADO_OPTIONS),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoHomes(HomeAssistantError):
    """Error to indicate the account has no homes."""
