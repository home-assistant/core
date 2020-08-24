"""Config flow for the Total Connect component."""
from total_connect_client import TotalConnectClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import (  # pylint: disable=unused-import
    CONF_USERCODES,
    DEFAULT_USERCODE,
    DOMAIN,
)


class TotalConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Total Connect config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.username = None
        self.password = None
        self.client = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]
            usercodes = user_input.get(CONF_USERCODES)

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            client = await self.hass.async_add_executor_job(
                TotalConnectClient.TotalConnectClient, username, password, usercodes
            )

            if client.is_valid_credentials():
                # username/password valid so show user locations
                self.username = username
                self.password = password
                self.client = client
                return await self.async_step_locations(usercodes)
            # authentication failed / invalid
            errors["base"] = "invalid_auth"

        data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_locations(self, usercodes=None):
        """Handle the user locations and associated usercodes."""
        errors = {}

        if usercodes is not None:
            for location in usercodes:
                valid = await self.hass.async_add_executor_job(
                    self.client.locations[int(location)].set_usercode,
                    usercodes[location],
                )
                if not valid:
                    errors[location] = "usercode"

            if not errors:
                return self.async_create_entry(
                    title="Total Connect",
                    data={
                        CONF_USERNAME: self.username,
                        CONF_PASSWORD: self.password,
                        CONF_USERCODES: usercodes,
                    },
                )

        # show the locations with DEFAULT_USERCODE already entered
        location_codes = {}
        for location_id in self.client.locations:
            location_codes[vol.Required(location_id, default=DEFAULT_USERCODE)] = str

        data_schema = vol.Schema(location_codes)
        return self.async_show_form(
            step_id="locations",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"base": "description"},
        )

    async def async_step_import(self, user_input):
        """Import a config entry."""
        return await self.async_step_user(user_input)
