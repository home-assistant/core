"""The Things Network's integration config flow."""

from collections.abc import Mapping
import logging
from typing import Any

from ttn_client import TTNAuthError, TTNClient
import voluptuous as vol

from homeassistant.config_entries import (
    HANDLERS,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
)

from .const import CONF_API_KEY, CONF_APP_ID, CONF_HOSTNAME, DOMAIN, TTN_API_HOSTNAME

_LOGGER = logging.getLogger(__name__)


@HANDLERS.register(DOMAIN)
class TTNFlowHandler(ConfigFlow):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self.__hostname: str = TTN_API_HOSTNAME
        self.__app_id: str | None = None
        self.__access_key: str | None = None
        self.__reauth_entry: ConfigEntry | None = None

    @property
    def schema(self) -> vol.Schema:
        """Return current schema."""

        return vol.Schema(
            {
                vol.Required(CONF_HOSTNAME, default=self.__hostname): str,
                vol.Required(CONF_APP_ID, default=self.__app_id): str,
                vol.Required(CONF_API_KEY, default=self.__access_key): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated config flow."""
        errors = {}
        if user_input is not None:
            self.__hostname = user_input[CONF_HOSTNAME]
            self.__app_id = user_input[CONF_APP_ID]
            self.__access_key = user_input[CONF_API_KEY]

            connection_error = await self.__connection_error

            if connection_error:
                errors["base"] = connection_error
            else:
                return await self.__create_or_update_entry(user_input)

        return self.async_show_form(
            step_id="user", data_schema=self.schema, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by a reauth event."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        assert entry is not None
        self.__reauth_entry = entry
        self.__hostname = entry.data[CONF_HOSTNAME]
        self.__app_id = entry.data[CONF_APP_ID]
        self.__access_key = entry.data[CONF_API_KEY]
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"app_id": self.__app_id},
            )
        return await self.async_step_user()

    async def __create_or_update_entry(
        self, data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Create or update TTN entry."""

        if self.__reauth_entry:
            return self.async_update_reload_and_abort(
                self.__reauth_entry,
                data=self.__reauth_entry.data | data,
                reason="reauth_successful",
            )
        if not self.unique_id:
            await self.async_set_unique_id(self.__app_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=str(self.__app_id),
            data=data,
        )

    @property
    async def __connection_error(self) -> str | None:
        """Test if we can connect with the given settings."""

        try:
            client = TTNClient(
                self.__hostname,
                self.__app_id,
                self.__access_key,
                0,
            )
            await client.fetch_data()
            return None
        except TTNAuthError:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            _LOGGER.error("TTNAuthError")
            return "invalid_auth"
