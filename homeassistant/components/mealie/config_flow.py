"""Config flow for Mealie."""

from typing import Any

from aiomealie import MealieAuthenticationError, MealieClient, MealieConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN, CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, LOGGER

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
            client = MealieClient(
                user_input[CONF_HOST],
                token=user_input[CONF_API_TOKEN],
                session=async_get_clientsession(self.hass),
            )
            try:
                info = await client.get_user_info()
            except MealieConnectionError:
                errors["base"] = "cannot_connect"
            except MealieAuthenticationError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unexpected error")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(info.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Mealie",
                    data=user_input,
                )
        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )
