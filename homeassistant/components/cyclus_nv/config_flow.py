"""Config flow to configure the Cyclus NV integration."""

from __future__ import annotations

from typing import Any

from cyclus.cyclus import CyclusClient
from cyclus.exceptions import CyclusError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_BAG_ID, CONF_HOUSE_NUMBER, CONF_ZIPCODE, DOMAIN


class CyclusNVFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a Cyclus NV config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = CyclusClient(session=session)

            try:
                bag_id = await client.get_bag_id(
                    zipcode=user_input[CONF_ZIPCODE],
                    house_number=int(user_input[CONF_HOUSE_NUMBER]),
                )
            except CyclusError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(bag_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"{user_input[CONF_ZIPCODE]} {user_input[CONF_HOUSE_NUMBER]}",
                    data={
                        CONF_ZIPCODE: user_input[CONF_ZIPCODE],
                        CONF_HOUSE_NUMBER: user_input[CONF_HOUSE_NUMBER],
                        CONF_BAG_ID: bag_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ZIPCODE): str,
                    vol.Required(CONF_HOUSE_NUMBER): str,
                }
            ),
            errors=errors,
        )
