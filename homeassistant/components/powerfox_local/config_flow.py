"""Config flow for Powerfox Local integration."""

from __future__ import annotations

from typing import Any

from powerfox import PowerfoxAuthenticationError, PowerfoxConnectionError, PowerfoxLocal
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_KEY): str,
    }
)


class PowerfoxLocalConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Powerfox Local."""

    _host: str
    _api_key: str
    _device_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._api_key = user_input[CONF_API_KEY]
            self._device_id = self._api_key

            try:
                await self._async_validate_connection()
            except PowerfoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except PowerfoxConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self._async_create_entry()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle zeroconf discovery."""
        self._host = discovery_info.host
        self._device_id = discovery_info.properties["id"]
        self._api_key = self._device_id

        try:
            await self._async_validate_connection()
        except PowerfoxAuthenticationError, PowerfoxConnectionError:
            return self.async_abort(reason="cannot_connect")

        self.context["title_placeholders"] = {
            "name": f"Poweropti ({self._device_id[-5:]})"
        }

        self._set_confirm_only()
        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={"host": self._host},
        )

    async def async_step_zeroconf_confirm(
        self, _: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a confirmation flow for zeroconf discovery."""
        return self._async_create_entry()

    def _async_create_entry(self) -> ConfigFlowResult:
        """Create a config entry."""
        return self.async_create_entry(
            title=f"Poweropti ({self._device_id[-5:]})",
            data={
                CONF_HOST: self._host,
                CONF_API_KEY: self._api_key,
            },
        )

    async def _async_validate_connection(self) -> None:
        """Validate the connection and set unique ID."""
        client = PowerfoxLocal(
            host=self._host,
            api_key=self._api_key,
            session=async_get_clientsession(self.hass),
        )
        await client.value()

        await self.async_set_unique_id(self._device_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})
