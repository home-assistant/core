"""Config flow for the Total Connect component."""
from total_connect_client import TotalConnectClient
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_USERCODES, DOMAIN

CONF_LOCATION = "location"

PASSWORD_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class TotalConnectConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Total Connect config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.username = None
        self.password = None
        self.usercodes = {}
        self.client = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Validate user input
            username = user_input[CONF_USERNAME]
            password = user_input[CONF_PASSWORD]

            await self.async_set_unique_id(username)
            self._abort_if_unique_id_configured()

            client = await self.hass.async_add_executor_job(
                TotalConnectClient.TotalConnectClient, username, password, None
            )

            if client.is_valid_credentials():
                # username/password valid so show user locations
                self.username = username
                self.password = password
                self.client = client
                return await self.async_step_locations()
            # authentication failed / invalid
            errors["base"] = "invalid_auth"

        data_schema = vol.Schema(
            {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_locations(self, user_entry=None):
        """Handle the user locations and associated usercodes."""
        errors = {}
        if user_entry is not None:
            for location_id in self.usercodes:
                if self.usercodes[location_id] is None:
                    valid = await self.hass.async_add_executor_job(
                        self.client.locations[location_id].set_usercode,
                        user_entry[CONF_USERCODES],
                    )
                    if valid:
                        self.usercodes[location_id] = user_entry[CONF_USERCODES]
                    else:
                        errors[CONF_LOCATION] = "usercode"
                    break

            complete = True
            for location_id in self.usercodes:
                if self.usercodes[location_id] is None:
                    complete = False

            if not errors and complete:
                return self.async_create_entry(
                    title="Total Connect",
                    data={
                        CONF_USERNAME: self.username,
                        CONF_PASSWORD: self.password,
                        CONF_USERCODES: self.usercodes,
                    },
                )
        else:
            for location_id in self.client.locations:
                self.usercodes[location_id] = None

        # show the next location that needs a usercode
        location_codes = {}
        location_for_user = ""
        for location_id in self.usercodes:
            if self.usercodes[location_id] is None:
                location_for_user = location_id
                location_codes[
                    vol.Required(
                        CONF_USERCODES,
                        default="0000",
                    )
                ] = str
                break

        data_schema = vol.Schema(location_codes)
        return self.async_show_form(
            step_id="locations",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"location_id": location_for_user},
        )

    async def async_step_reauth(self, config):
        """Perform reauth upon an authentication error or no usercode."""
        self.username = config[CONF_USERNAME]
        self.usercodes = config[CONF_USERCODES]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        """Dialog that informs the user that reauth is required."""
        errors = {}
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=PASSWORD_DATA_SCHEMA,
            )

        client = await self.hass.async_add_executor_job(
            TotalConnectClient.TotalConnectClient,
            self.username,
            user_input[CONF_PASSWORD],
            self.usercodes,
        )

        if not client.is_valid_credentials():
            errors["base"] = "invalid_auth"
            return self.async_show_form(
                step_id="reauth_confirm",
                errors=errors,
                data_schema=PASSWORD_DATA_SCHEMA,
            )

        existing_entry = await self.async_set_unique_id(self.username)
        new_entry = {
            CONF_USERNAME: self.username,
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_USERCODES: self.usercodes,
        }
        self.hass.config_entries.async_update_entry(existing_entry, data=new_entry)

        self.hass.async_create_task(
            self.hass.config_entries.async_reload(existing_entry.entry_id)
        )

        return self.async_abort(reason="reauth_successful")
