"""Config flow to configure the eGauge integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from egauge_async.json.client import EgaugeAuthenticationError, EgaugeJsonClient
from httpx import ConnectError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.httpx_client import get_async_client

from . import _build_client_url
from .const import DOMAIN, LOGGER


class EgaugeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an eGauge config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            client = EgaugeJsonClient(
                base_url=_build_client_url(user_input[CONF_HOST], user_input[CONF_SSL]),
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                client=get_async_client(
                    self.hass, verify_ssl=user_input[CONF_VERIFY_SSL]
                ),
            )
            try:
                serial_number = await client.get_device_serial_number()
            except EgaugeAuthenticationError:
                errors["base"] = "invalid_auth"
            except ConnectError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(serial_number)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="eGauge", data=user_input)
        else:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input.get(CONF_HOST)): str,
                    vol.Required(
                        CONF_USERNAME, default=user_input.get(CONF_USERNAME)
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_SSL, default=True): bool,
                    vol.Required(CONF_VERIFY_SSL, default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle initiation of re-authentication with an eGauge device."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication with an eGauge device."""
        errors = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            client = EgaugeJsonClient(
                base_url=_build_client_url(
                    reauth_entry.data[CONF_HOST], reauth_entry.data[CONF_SSL]
                ),
                username=user_input[CONF_USERNAME],
                password=user_input[CONF_PASSWORD],
                client=get_async_client(
                    self.hass, verify_ssl=reauth_entry.data[CONF_VERIFY_SSL]
                ),
            )
            try:
                await client.get_device_serial_number()
            except EgaugeAuthenticationError:
                errors["base"] = "invalid_auth"
            except ConnectError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_HOST: reauth_entry.data[CONF_HOST],
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SSL: reauth_entry.data[CONF_SSL],
                        CONF_VERIFY_SSL: reauth_entry.data[CONF_VERIFY_SSL],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )
