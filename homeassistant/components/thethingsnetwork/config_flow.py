"""The Things Network's integration config flow."""

from collections.abc import Mapping
import logging
from typing import Any

from ttn_client import TTNAuthError, TTNClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult

from .const import CONF_API_KEY, CONF_APP_ID, CONF_HOSTNAME, DOMAIN, TTN_API_HOSTNAME

_LOGGER = logging.getLogger(__name__)


class TTNFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._user_input: Mapping[str, Any] = {}
        self._user_input[CONF_HOSTNAME] = TTN_API_HOSTNAME
        self._reauth_entry: ConfigEntry | None = None

    @property
    def schema(self) -> vol.Schema:
        """Return current schema."""

        return vol.Schema(
            {
                vol.Required(
                    CONF_HOSTNAME, default=self._user_input[CONF_HOSTNAME]
                ): str,
                vol.Required(
                    CONF_APP_ID, default=self._user_input.get(CONF_APP_ID)
                ): str,
                vol.Required(
                    CONF_API_KEY, default=self._user_input.get(CONF_API_KEY)
                ): str,
            }
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated config flow."""
        errors = {}
        if user_input is not None:
            self._user_input = user_input

            connection_error = await self._connection_error

            if connection_error:
                errors["base"] = connection_error
            else:
                return await self._create_or_update_entry(user_input)

        return self.async_show_form(
            step_id="user", data_schema=self.schema, errors=errors
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by a reauth event."""

        self._user_input = user_input
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema({}),
                description_placeholders={"app_id": self._user_input[CONF_APP_ID]},
            )
        return await self.async_step_user()

    async def _create_or_update_entry(
        self, data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Create or update TTN entry."""

        if self._reauth_entry:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data=self._reauth_entry.data | data,
                reason="reauth_successful",
            )
        if not self.unique_id:
            await self.async_set_unique_id(data[CONF_APP_ID])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=str(data[CONF_APP_ID]),
            data=data,
        )

    @property
    async def _connection_error(self) -> str | None:
        """Test if we can connect with the given settings."""

        try:
            client = TTNClient(
                self._user_input[CONF_HOSTNAME],
                self._user_input[CONF_APP_ID],
                self._user_input[CONF_API_KEY],
                0,
            )
            await client.fetch_data()
            return None
        except TTNAuthError:
            # Raising ConfigEntryAuthFailed will cancel future updates
            # and start a config flow with SOURCE_REAUTH (async_step_reauth)
            _LOGGER.error("TTNAuthError")
            return "invalid_auth"
