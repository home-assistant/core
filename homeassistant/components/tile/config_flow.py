"""Config flow to configure the Tile integration."""
from pytile import async_login
from pytile.errors import TileError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN  # pylint: disable=unused-import

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class TileFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Tile config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            await async_login(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session=session
            )
        except TileError:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)
