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

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_HOME_ASSISTANT_ACCESS_TOKEN,
    CONF_LOCAL_ACCESS_TOKEN,
    DOMAIN,
    NAME,
)


async def validate_input(user_input: dict[str, Any]) -> bool:
    """Validate the user input allows us to connect."""
    pak = user_input.get(CONF_ACCESS_TOKEN, "")
    host = user_input.get(CONF_HOST, "")
    local_access_token = user_input.get(CONF_LOCAL_ACCESS_TOKEN, "")
    tedee_client = TedeeClient(pak, local_access_token, host)

    try:
        await tedee_client.get_locks()
    except (TedeeAuthException, TedeeLocalAuthException) as ex:
        raise InvalidAuth from ex
    except (TedeeClientException, Exception) as ex:
        raise CannotConnect from ex
    return True


async def get_local_bridge(host: str, local_access_token: str) -> TedeeBridge:
    """Get the serial number of the local bridge."""
    tedee_client = TedeeClient(local_token=local_access_token, local_ip=host)
    try:
        return await tedee_client.get_local_bridge()
    except (TedeeClientException, Exception) as ex:
        raise CannotConnect from ex


class TedeeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tedee."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict = {}
        self._reload: bool = False
        self._previous_step_data: dict = {}
        self._config: dict = {}
        self._local_bridge_name: str = ""
        self._bridges: list[TedeeBridge] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict = {}
        local_bridge: TedeeBridge | None = None

        if user_input is not None:
            try:
                await validate_input(user_input)
                local_bridge = await get_local_bridge(
                    user_input[CONF_HOST], user_input[CONF_LOCAL_ACCESS_TOKEN]
                )
                await self.async_set_unique_id(local_bridge.serial)
                self._abort_if_unique_id_configured()
            except CannotConnect:
                errors[CONF_HOST] = "invalid_host"
            except InvalidAuth:
                errors[CONF_LOCAL_ACCESS_TOKEN] = "invalid_api_key"

            if not errors:
                return self.async_create_entry(title=NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_LOCAL_ACCESS_TOKEN): str,
                    vol.Optional(CONF_HOME_ASSISTANT_ACCESS_TOKEN): str,
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
                await validate_input(self._config | user_input)
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


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
