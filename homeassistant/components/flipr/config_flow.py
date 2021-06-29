"""Config flow for Flipr integration."""
from __future__ import annotations

import logging

from flipr_api import FliprAPIRestClient
from requests.exceptions import HTTPError, Timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import CONF_FLIPR_ID, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipr."""

    VERSION = 1

    _username: str | None = None
    _password: str | None = None
    _flipr_id: str | None = None
    _possible_flipr_ids: list[str] | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self._show_setup_form()

        self._username = user_input[CONF_EMAIL]
        self._password = user_input[CONF_PASSWORD]

        errors = {}
        if not self._flipr_id:
            try:
                flipr_ids = await self._authenticate_and_search_flipr()
            except HTTPError:
                errors["base"] = "invalid_auth"
            except (Timeout, ConnectionError):
                errors["base"] = "cannot_connect"
            except Exception as exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
                _LOGGER.exception(exception)

            if not errors and len(flipr_ids) == 0:
                # No flipr_id found. Tell the user with an error message.
                errors["base"] = "no_flipr_id_found"

            if errors:
                return self._show_setup_form(errors)

            if len(flipr_ids) == 1:
                self._flipr_id = flipr_ids[0]
            else:
                # If multiple flipr found (rare case), we ask the user to choose one in a select box.
                # The user will have to run config_flow as many times as many fliprs he has.
                self._possible_flipr_ids = flipr_ids
                return await self.async_step_flipr_id()

        # Check if already configured
        await self.async_set_unique_id(self._flipr_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=self._flipr_id,
            data={
                CONF_EMAIL: self._username,
                CONF_PASSWORD: self._password,
                CONF_FLIPR_ID: self._flipr_id,
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

    async def _authenticate_and_search_flipr(self) -> list[str]:
        """Validate the username and password provided and searches for a flipr id."""
        client = await self.hass.async_add_executor_job(
            FliprAPIRestClient, self._username, self._password
        )

        flipr_ids = await self.hass.async_add_executor_job(client.search_flipr_ids)

        return flipr_ids

    async def async_step_flipr_id(self, user_input=None):
        """Handle the initial step."""
        if not user_input:
            # Creation of a select with the proposal of flipr ids values found by API.
            flipr_ids_for_form = {}
            for flipr_id in self._possible_flipr_ids:
                flipr_ids_for_form[flipr_id] = f"{flipr_id}"

            return self.async_show_form(
                step_id="flipr_id",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_FLIPR_ID): vol.All(
                            vol.Coerce(str), vol.In(flipr_ids_for_form)
                        )
                    }
                ),
            )

        # Get chosen flipr_id.
        self._flipr_id = user_input[CONF_FLIPR_ID]

        return await self.async_step_user(
            {
                CONF_EMAIL: self._username,
                CONF_PASSWORD: self._password,
                CONF_FLIPR_ID: self._flipr_id,
            }
        )
