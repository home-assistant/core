"""Config flow for Adax integration."""

from __future__ import annotations

import logging
from typing import Any

import adax
import adax_local
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_UNIQUE_ID,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ACCOUNT_ID,
    CLOUD,
    CONNECTION_TYPE,
    DOMAIN,
    LOCAL,
    WIFI_PSWD,
    WIFI_SSID,
)

_LOGGER = logging.getLogger(__name__)


class AdaxConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Adax."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        data_schema = vol.Schema(
            {
                vol.Required(CONNECTION_TYPE, default=CLOUD): vol.In(
                    (
                        CLOUD,
                        LOCAL,
                    )
                )
            }
        )

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
            )

        if user_input[CONNECTION_TYPE] == LOCAL:
            return await self.async_step_local()
        return await self.async_step_cloud()

    async def async_step_local(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the local step."""
        data_schema = vol.Schema(
            {vol.Required(WIFI_SSID): str, vol.Required(WIFI_PSWD): str}
        )
        if user_input is None:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
            )

        wifi_ssid = user_input[WIFI_SSID].replace(" ", "")
        wifi_pswd = user_input[WIFI_PSWD].replace(" ", "")
        configurator = adax_local.AdaxConfig(wifi_ssid, wifi_pswd)

        try:
            device_configured = await configurator.configure_device()
        except adax_local.HeaterNotAvailable:
            return self.async_abort(reason="heater_not_available")
        except adax_local.HeaterNotFound:
            return self.async_abort(reason="heater_not_found")
        except adax_local.InvalidWifiCred:
            return self.async_abort(reason="invalid_auth")

        if not device_configured:
            return self.async_show_form(
                step_id="local",
                data_schema=data_schema,
                errors={"base": "cannot_connect"},
            )

        unique_id = str(configurator.mac_id)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_IP_ADDRESS: configurator.device_ip,
                CONF_TOKEN: configurator.access_token,
                CONF_UNIQUE_ID: unique_id,
                CONNECTION_TYPE: LOCAL,
            },
        )

    async def async_step_cloud(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the cloud step."""
        data_schema = vol.Schema(
            {vol.Required(ACCOUNT_ID): int, vol.Required(CONF_PASSWORD): str}
        )
        if user_input is None:
            return self.async_show_form(step_id="cloud", data_schema=data_schema)

        errors = {}

        await self.async_set_unique_id(str(user_input[ACCOUNT_ID]))
        self._abort_if_unique_id_configured()

        account_id = user_input[ACCOUNT_ID]
        password = user_input[CONF_PASSWORD].replace(" ", "")

        token = await adax.get_adax_token(
            async_get_clientsession(self.hass), account_id, password
        )
        if token is None:
            _LOGGER.debug("Adax: Failed to login to retrieve token")
            errors["base"] = "cannot_connect"
            return self.async_show_form(
                step_id="cloud",
                data_schema=data_schema,
                errors=errors,
            )

        return self.async_create_entry(
            title=str(user_input[ACCOUNT_ID]),
            data={
                ACCOUNT_ID: account_id,
                CONF_PASSWORD: password,
                CONNECTION_TYPE: CLOUD,
            },
        )
