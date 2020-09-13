"""Config flow for NIU."""
import logging

from niu import NiuAPIException, NiuCloud, NiuNetException, NiuServerException
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)


class NiuConfigFlow(config_entries.ConfigFlow):
    """Config Flow for NIU."""

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input=None):
        """Handle the start of the config flow."""

        if not user_input:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        try:
            token = await setup_account(self.hass, user_input)
        except (NiuAPIException, NiuNetException, NiuServerException):
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base", "connection_error"},
            )

        return self.async_create_entry(
            title=user_input[CONF_USERNAME], data={CONF_TOKEN: token},
        )


async def setup_account(hass, conf: dict):
    """Set up a NIU account."""

    account = NiuCloud(username=conf[CONF_USERNAME], password=conf[CONF_PASSWORD])

    return await account.connect()
