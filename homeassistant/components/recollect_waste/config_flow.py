"""Config flow for ReCollect Waste integration."""

from __future__ import annotations

from typing import Any

from aiorecollect.client import Client
from aiorecollect.errors import RecollectError
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_FRIENDLY_NAME
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .const import CONF_PLACE_ID, CONF_SERVICE_ID, DOMAIN, LOGGER

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_PLACE_ID): str, vol.Required(CONF_SERVICE_ID): str}
)


class RecollectWasteConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ReCollect Waste."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> RecollectWasteOptionsFlowHandler:
        """Define the config flow to handle options."""
        return RecollectWasteOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            await client.async_get_pickup_events()
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


class RecollectWasteOptionsFlowHandler(OptionsFlow):
    """Handle a Recollect Waste options flow."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_FRIENDLY_NAME,
                        default=self.config_entry.options.get(CONF_FRIENDLY_NAME),
                    ): bool
                }
            ),
        )
