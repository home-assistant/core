"""Config flow to configure the OVO Energy integration."""
import aiohttp
from ovoenergy.ovoenergy import OVOEnergy
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN  # pylint: disable=unused-import

REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})
USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class OVOEnergyFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a OVO Energy config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize the flow."""
        self.username = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initiated by the user."""
        errors = {}
        if user_input is not None:
            client = OVOEnergy()
            try:
                authenticated = await client.authenticate(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            else:
                if authenticated:
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=client.username,
                        data={
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                        },
                    )

                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, user_input):
        """Handle configuration by re-auth."""
        errors = {}

        if user_input and user_input.get(CONF_USERNAME):
            self.username = user_input[CONF_USERNAME]

        # pylint: disable=no-member
        self.context["title_placeholders"] = {CONF_USERNAME: self.username}

        if user_input is not None and user_input.get(CONF_PASSWORD) is not None:
            client = OVOEnergy()
            try:
                authenticated = await client.authenticate(
                    self.username, user_input[CONF_PASSWORD]
                )
            except aiohttp.ClientError:
                errors["base"] = "connection_error"
            else:
                if authenticated:
                    await self.async_set_unique_id(self.username)

                    for entry in self._async_current_entries():
                        if entry.unique_id == self.unique_id:
                            self.hass.config_entries.async_update_entry(
                                entry,
                                data={
                                    CONF_USERNAME: self.username,
                                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                                },
                            )
                            return self.async_abort(reason="reauth_successful")

                errors["base"] = "authorization_error"

        return self.async_show_form(
            step_id="reauth", data_schema=REAUTH_SCHEMA, errors=errors
        )
