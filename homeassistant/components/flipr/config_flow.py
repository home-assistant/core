"""Config flow for Flipr integration."""
import logging

import voluptuous as vol

from requests.exceptions import HTTPError

from homeassistant import config_entries, core, exceptions

from flipr_api import FliprAPIRestClient

from .const import DOMAIN  # pylint:disable=unused-import
from .const import CONF_USERNAME, CONF_PASSWORD, CONF_FLIPR_ID

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipr."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Flipr config flow."""
        self._username = None
        self._password = None
        self._flipr_id = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        _LOGGER.debug("Starting async_step_user")

        if user_input is None:
            return self._show_setup_form()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        errors = {}
        try:
            self._flipr_id = await self._authenticate_and_search_flipr()
        except HTTPError:
            errors["base"] = "invalid_auth"
            return self._show_setup_form(errors)

        if not self._flipr_id:
            # No Flipr found : asks the user to enter it.
            return await self.async_step_flipr_id()

        # No check for data retrieval here.

        # Check if already configured
        await self.async_set_unique_id("FLIPR_with_ID_" + self._flipr_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="Flipr device - " + self._flipr_id,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_FLIPR_ID: self._flipr_id,
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

    async def _authenticate_and_search_flipr(self):
        """Validate the username and password provided.
        And searches for a flipr id.
        """

        client = await self.hass.async_add_executor_job(
            FliprAPIRestClient, self._username, self._password
        )

        _LOGGER.debug("FliprAPIRestClient called. " + str(client))

        flipr_ids = await self.hass.async_add_executor_job(client.search_flipr_ids)
        _LOGGER.debug("Flipr_ids found = " + str(flipr_ids))

        if len(flipr_ids) > 0:
            # Return the found flipr_id as a string
            return flipr_ids[0]

        return None

    async def async_step_flipr_id(self, user_input=None):
        """Handle the initial step."""

        _LOGGER.debug("Starting async_step_flipr_id")

        # TODO : demander la saisie du fliprId
        if not user_input:
            return self.async_show_form(
                step_id="flipr_id",
                data_schema=vol.Schema({vol.Required(CONF_FLIPR_ID): str}),
            )

        return await self.async_step_user(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_FLIPR_ID: self._flipr_id,
            }
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)
