"""Config flow for Tedee integration."""
from collections.abc import Mapping
from typing import Any

from pytedee_async import (
    TedeeAuthException,
    TedeeClient,
    TedeeClientException,
    TedeeLocalAuthException,
)
from pytedee_async.bridge import TedeeBridge
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_LOCAL_ACCESS_TOKEN, DOMAIN, NAME


class TedeeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tedee."""

    _config: dict[str, Any] = {}

    async def get_tedee_bridge(self, user_input: dict[str, Any]) -> TedeeBridge:
        """Validate the user input allows us to connect."""
        host = user_input[CONF_HOST]
        local_access_token = user_input[CONF_LOCAL_ACCESS_TOKEN]
        tedee_client = TedeeClient(local_token=local_access_token, local_ip=host)
        try:
            return await tedee_client.get_local_bridge()
        except (TedeeAuthException, TedeeLocalAuthException):
            raise InvalidAuth
        except TedeeClientException:
            raise CannotConnect

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                local_bridge = await self.get_tedee_bridge(user_input)
            except CannotConnect:
                errors[CONF_HOST] = "invalid_host"
            except InvalidAuth:
                errors[CONF_LOCAL_ACCESS_TOKEN] = "invalid_api_key"
            else:
                await self.async_set_unique_id(local_bridge.serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_LOCAL_ACCESS_TOKEN): str,
                }
            ),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._config = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        errors = {}

        if user_input is not None:
            try:
                await self.get_tedee_bridge(self._config | user_input)
            except InvalidAuth:
                errors[CONF_LOCAL_ACCESS_TOKEN] = "invalid_api_key"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            if not errors:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self._config |= user_input
                self.hass.config_entries.async_update_entry(entry, data=self._config)  # type: ignore[arg-type]
                await self.hass.config_entries.async_reload(self.context["entry_id"])
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_LOCAL_ACCESS_TOKEN,
                        default=self._config.get(CONF_LOCAL_ACCESS_TOKEN),
                    ): str
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
