"""Config flow for SunSynk integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from . import SunSynkConfigEntry
from .auth import async_authenticate
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_PLANT_IGNORE_LIST,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL,
    REGIONS,
    SunSynkAuthError,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_REGION, default=0): vol.In(REGIONS),
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    region_idx = data[CONF_REGION]
    email = data[CONF_EMAIL]
    password = data[CONF_PASSWORD]

    try:
        await async_authenticate(
            email,
            password,
            region_idx,
            async_client=get_async_client(hass),
        )
    except SunSynkAuthError as err:
        _LOGGER.error("Failed to authenticate with SunSynk: %s", err)
        raise InvalidAuth from err
    except Exception as err:
        _LOGGER.error("Cannot connect to SunSynk: %s", err)
        raise CannotConnect from err

    return {"title": f"SunSynk ({email})"}


class ConfigFlow(config_entries.ConfigFlow, domain="sunsynk"):
    """Handle a config flow for SunSynk."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SunSynkConfigEntry,
    ) -> OptionsFlow:
        """Get the options flow handler."""
        return SunSynkOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors: dict[str, str] = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONF_EMAIL])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reconfigure")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL])
                self._abort_if_unique_id_configured(
                    updates=user_input,
                    reload_on_update=True,
                )
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=info["title"],
                    data=user_input,
                )

        current = reconfigure_entry.data
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REGION, default=current.get(CONF_REGION, 0)
                    ): vol.In(REGIONS),
                    vol.Required(CONF_EMAIL, default=current.get(CONF_EMAIL, "")): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when credentials become invalid."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            new_data = {**reauth_entry.data, **user_input}

            try:
                await validate_input(self.hass, new_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )


class SunSynkOptionsFlow(OptionsFlow):
    """Handle options for SunSynk."""

    def __init__(self, config_entry: SunSynkConfigEntry) -> None:
        """Initialise options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
                    vol.Optional(
                        CONF_PLANT_IGNORE_LIST,
                        default=current.get(CONF_PLANT_IGNORE_LIST, ""),
                    ): str,
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

    translation_key = "cannot_connect"


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

    translation_key = "invalid_auth"
