"""Config flow for Flipr integration."""
from typing import List

from flipr_api import FliprAPIRestClient
from requests.exceptions import HTTPError
import voluptuous as vol

from homeassistant import config_entries

from .const import CONF_FLIPR_ID, CONF_PASSWORD, CONF_USERNAME
from .const import DOMAIN  # pylint:disable=unused-import
from .crypt_util import encrypt_data


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Flipr."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize Flipr config flow."""
        self._username = None
        self._password = None
        self._flipr_id = None
        self._possible_flipr_ids = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self._show_setup_form()

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        if not self._flipr_id:
            try:
                flipr_ids = await self._authenticate_and_search_flipr()
            except HTTPError:
                errors = {}
                errors["base"] = "invalid_auth"
                return self._show_setup_form(errors)

            if len(flipr_ids) == 1:
                self._flipr_id = flipr_ids[0]
            else:
                # No Flipr or multiple found : asks the user to enter it or select it.
                self._possible_flipr_ids = flipr_ids
                return await self.async_step_flipr_id()

        # No check for data retrieval here.

        # Check if already configured
        await self.async_set_unique_id("FLIPR_with_ID_" + self._flipr_id)
        self._abort_if_unique_id_configured()

        # Encrypt password before storing it in the config json file.
        crypted_password = encrypt_data(self._password, self._flipr_id)

        return self.async_create_entry(
            title="Flipr device - " + self._flipr_id,
            data={
                CONF_USERNAME: self._username,
                CONF_PASSWORD: crypted_password,
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

    async def _authenticate_and_search_flipr(self) -> List[str]:
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
            if len(self._possible_flipr_ids) > 1:
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
            # Else : no flipr_id found. Allow the user to enter it.
            # It may cause no data found afterwards in metrics...
            return self.async_show_form(
                step_id="flipr_id",
                data_schema=vol.Schema({vol.Required(CONF_FLIPR_ID): str}),
            )

        # Get chosen or entered flipr_id.
        self._flipr_id = user_input[CONF_FLIPR_ID]

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
