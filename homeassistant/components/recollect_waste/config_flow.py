"""Config flow for Recollect Waste integration."""
from aiorecollect.client import Client
from aiorecollect.errors import RecollectError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client

from .const import (  # pylint:disable=unused-import
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
    LOGGER,
)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLACE_ID): str, vol.Required(CONF_SERVICE_ID): str}
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Recollect Waste."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_import(self, import_config: dict = None) -> dict:
        """Handle configuration via YAML import."""
        return await self.async_step_user(import_config)

    async def async_step_user(self, user_input: dict = None) -> dict:
        """Handle configuration via the UI."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA, errors={}
            )

        unique_id = f"{user_input[CONF_PLACE_ID]}, {user_input[CONF_SERVICE_ID]}"

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        session = aiohttp_client.async_get_clientsession(self.hass)
        client = Client(
            user_input[CONF_PLACE_ID], user_input[CONF_SERVICE_ID], session=session
        )

        try:
            await client.async_get_next_pickup_event()
        except RecollectError as err:
            LOGGER.error("Error during setup of integration: %s", err)
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_place_or_service_id"},
            )

        return self.async_create_entry(
            title=unique_id,
            data={
                CONF_PLACE_ID: user_input[CONF_PLACE_ID],
                CONF_SERVICE_ID: user_input[CONF_SERVICE_ID],
            },
        )
