"""Config flow for Flipr integration."""
import logging
from typing import List

from flipr_api import FliprAPIRestClient
from requests.exceptions import HTTPError, Timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import CONF_FLIPR_IDS
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipr."""

    VERSION = 1

    _username: str | None = None
    _password: str | None = None
    _flipr_ids: str | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self._show_setup_form()

        self._username = user_input[CONF_EMAIL]
        self._password = user_input[CONF_PASSWORD]

        errors = {}
        if not self._flipr_ids:
            try:
                flipr_ids = await self._authenticate_and_search_flipr()
            except HTTPError:
                errors = {}
                errors["base"] = "invalid_auth"
                return self._show_setup_form(errors)
            except (Timeout, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(exception)

            if len(flipr_ids) == 0:
                # No flipr_id found. Tell the user with an error message.
                errors["base"] = "no_flipr_id_found"

            if errors:
                return self._show_setup_form(errors)

            # If multiple flipr found (rare case), we concatenate the ids to create multiple devices in this configuration.
            self._flipr_ids = ",".join(flipr_ids)

        # Check if already configured
        await self.async_set_unique_id(self._flipr_ids)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._flipr_ids,
            data={
                CONF_EMAIL: self._username,
                CONF_PASSWORD: self._password,
                CONF_FLIPR_IDS: self._flipr_ids,
            },
        )

    def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
            ),
            errors=errors,
        )

    async def _authenticate_and_search_flipr(self) -> List[str]:
        """Validate the username and password provided and searches for a flipr id."""
        client = await self.hass.async_add_executor_job(
            FliprAPIRestClient, self._username, self._password
        )

        flipr_ids = await self.hass.async_add_executor_job(client.search_flipr_ids)

        return flipr_ids
