"""The Things Network's integration config flow."""

from collections.abc import Mapping
import logging
from typing import Any

from ttn_client import TTNAuthError, TTNClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_APP_ID, DOMAIN, TTN_API_HOST

_LOGGER = logging.getLogger(__name__)


class TTNFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> ConfigFlowResult:
        """User initiated config flow."""

        errors = {}
        if user_input is not None:
            client = TTNClient(
                user_input[CONF_HOST],
                user_input[CONF_APP_ID],
                user_input[CONF_API_KEY],
                0,
            )
            try:
                await client.fetch_data()
            except TTNAuthError:
                _LOGGER.exception("Error authenticating with The Things Network")
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unknown error occurred")
                errors["base"] = "unknown"

            if not errors:
                # Create entry
                if self._reauth_entry:
                    return self.async_update_reload_and_abort(
                        self._reauth_entry,
                        data=user_input,
                        reason="reauth_successful",
                    )
                await self.async_set_unique_id(user_input[CONF_APP_ID])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=str(user_input[CONF_APP_ID]),
                    data=user_input,
                )

        # Show form for user to provide settings
        if not user_input:
            if self._reauth_entry:
                user_input = self._reauth_entry.data
            else:
                user_input = {CONF_HOST: TTN_API_HOST}

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_APP_ID): str,
                    vol.Required(CONF_API_KEY): TextSelector(
                        TextSelectorConfig(
                            type=TextSelectorType.PASSWORD, autocomplete="api_key"
                        )
                    ),
                }
            ),
            user_input,
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a flow initialized by a reauth event."""

        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()
