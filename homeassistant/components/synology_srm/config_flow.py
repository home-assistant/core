"""Config flow for Synology SRM integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import requests
import synology_srm
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .device_tracker import (
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SSL,
    DEFAULT_USERNAME,
    DOMAIN,
    SynologySRMConfigEntry,
    get_api,
)

_LOGGER = logging.getLogger(__name__)


class SynologySRMFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Synology SRM config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: SynologySRMConfigEntry,
    ) -> SynologySRMOptionsFlowHandler:
        """Get the options flow for this handler."""
        return SynologySRMOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})

            try:
                api = get_api(user_input)
                await self.hass.async_add_executor_job(api.mesh.get_system_info)
            except requests.exceptions.SSLError as err:
                _LOGGER.error("SSL error: %s", err)
                errors["base"] = "ssl_error"
            except requests.exceptions.HTTPError as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "cannot_connect"
            except synology_srm.http.SynologyApiError as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "invalid_auth"
            except synology_srm.http.SynologyHttpException as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception(
                    "Unknown error connecting with Synology SRM: %s",
                    user_input[CONF_HOST],
                )
                errors["base"] = "unknown"
            if not errors:
                return self.async_create_entry(
                    title=f"{'synology_srm'} ({user_input[CONF_HOST]})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Required(CONF_USERNAME, default=DEFAULT_USERNAME): cv.string,
                    vol.Required(CONF_PASSWORD): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
                    vol.Optional(CONF_VERIFY_SSL, default=False): cv.boolean,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=DEFAULT_SCAN_INTERVAL.total_seconds(),
                    ): vol.All(vol.Coerce(int), vol.Range(min=30)),
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            user_input = {**reauth_entry.data, **user_input}

            try:
                api = get_api(user_input)
                await self.hass.async_add_executor_job(api.mesh.get_system_info)
            except requests.exceptions.SSLError as err:
                _LOGGER.error("SSL error: %s", err)
                errors["base"] = "ssl_error"
            except requests.exceptions.HTTPError as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "cannot_connect"
            except synology_srm.http.SynologyApiError as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "invalid_auth"
            except synology_srm.http.SynologyHttpException as err:
                _LOGGER.error("Login failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception(
                    "Unknown error connecting with Synology SRM: %s",
                    user_input[CONF_HOST],
                )
                errors["base"] = "unknown"
            if not errors:
                return self.async_update_reload_and_abort(reauth_entry, data=user_input)

        return self.async_show_form(
            description_placeholders={CONF_USERNAME: reauth_entry.data[CONF_USERNAME]},
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): cv.string,
                }
            ),
            errors=errors,
        )


class SynologySRMOptionsFlowHandler(OptionsFlow):
    """Handle Synology SRM options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Synology SRM options."""
        return await self.async_step_device_tracker()

    async def async_step_device_tracker(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the device tracker options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = {
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=self.config_entry.options.get(CONF_SCAN_INTERVAL)
                or DEFAULT_SCAN_INTERVAL.total_seconds(),
            ): vol.All(vol.Coerce(int), vol.Range(min=30)),
        }

        return self.async_show_form(
            step_id="device_tracker", data_schema=vol.Schema(options)
        )
