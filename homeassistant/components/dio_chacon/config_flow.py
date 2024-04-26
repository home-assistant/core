"""Config flow for dio_chacon integration."""

from __future__ import annotations

import logging
from typing import Any

from dio_chacon_wifi_api import DIOChaconAPIClient
from dio_chacon_wifi_api.exceptions import DIOChaconAPIError, DIOChaconInvalidAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class DioChaconConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for dio_chacon."""

    _username: str
    _password: str
    _user_id: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self._show_setup_form()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        errors: dict[str, str] = {}
        try:
            self._user_id = await self._authenticate_and_search_user_id()
        except DIOChaconAPIError:
            errors["base"] = "cannot_connect"
        except DIOChaconInvalidAuthError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        if errors:
            return self._show_setup_form(errors)

        entry_id: str = "dio_chacon_" + self._user_id

        # Check if already configured
        await self.async_set_unique_id(entry_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Dio Chacon " + self._username,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_UNIQUE_ID: self._user_id,
            },
        )

    def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def _authenticate_and_search_user_id(self) -> str:
        """Validate the user name and password and retrieve the technical user id."""

        client = DIOChaconAPIClient(self._username, self._password)

        user_id: str = await client.get_user_id()

        await client.disconnect()

        return user_id
