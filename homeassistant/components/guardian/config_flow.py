"""Config flow for Elexa Guardian integration."""
from aioguardian import Client
from aioguardian.errors import GuardianError
import voluptuous as vol

from homeassistant import config_entries, core
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN, LOGGER  # pylint:disable=unused-import

DATA_SCHEMA = vol.Schema({CONF_IP_ADDRESS: str})


async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    async with Client(data[CONF_IP_ADDRESS]) as client:
        ping_data = await client.device.ping()

    return {
        "title": f"Elexa Guardian ({data[CONF_IP_ADDRESS]})",
        "uid": ping_data["data"]["uid"],
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elexa Guardian."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={}
            )

        await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
        self._abort_if_unique_id_configured()

        try:
            info = await validate_input(self.hass, user_input)
        except GuardianError as err:
            LOGGER.error("Error while connecting to unit: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={CONF_IP_ADDRESS: "cannot_connect"},
            )

        return self.async_create_entry(
            title=info["title"], data={"uid": info["uid"], **user_input}
        )
