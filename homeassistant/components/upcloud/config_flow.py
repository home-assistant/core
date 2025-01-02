"""Config flow for UpCloud."""

from __future__ import annotations

import logging
from typing import Any

import requests.exceptions
import upcloud_api
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import callback

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class UpCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """UpCloud config flow."""

    VERSION = 1

    username: str
    password: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle user initiated flow."""
        if user_input is None:
            return self._async_show_form(step_id="user")

        await self.async_set_unique_id(user_input[CONF_USERNAME])

        manager = upcloud_api.CloudManager(
            user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
        )

        errors = {}
        try:
            await self.hass.async_add_executor_job(manager.authenticate)
        except upcloud_api.UpCloudAPIError:
            errors["base"] = "invalid_auth"
            _LOGGER.debug("invalid_auth", exc_info=True)
        except requests.exceptions.RequestException:
            errors["base"] = "cannot_connect"
            _LOGGER.debug("cannot_connect", exc_info=True)

        if errors:
            return self._async_show_form(
                step_id="user", user_input=user_input, errors=errors
            )

        self._abort_if_unique_id_configured(
            updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
        )
        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)

    @callback
    def _async_show_form(
        self,
        step_id: str,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show our form."""
        if user_input is None:
            user_input = {}
        return self.async_show_form(
            step_id=step_id,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME, "")
                    ): str,
                    vol.Required(
                        CONF_PASSWORD, default=user_input.get(CONF_PASSWORD, "")
                    ): str,
                }
            ),
            errors=errors or {},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> UpCloudOptionsFlow:
        """Get options flow."""
        return UpCloudOptionsFlow()


class UpCloudOptionsFlow(OptionsFlow):
    """UpCloud options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle options flow."""

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL)
                    or DEFAULT_SCAN_INTERVAL.total_seconds(),
                ): vol.All(vol.Coerce(int), vol.Range(min=30)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=data_schema)
