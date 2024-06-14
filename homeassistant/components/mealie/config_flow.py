"""Config flow for Mealie."""

from typing import Any

from aiomealie import MealieClient, MealieError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_API_TOKEN): str,
    }
)


class MealieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Mealie config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}
        if user_input:
            session = async_get_clientsession(self.hass)
            client = MealieClient(user_input[CONF_HOST], session=session)
            try:
                await client.get_recipes()
            except MealieError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Mealie",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )
