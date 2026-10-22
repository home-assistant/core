"""Config flow for the WWS integration."""

from typing import Any, override

from pyenergiedock import DynamiT, EdAuthError, EdError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as HAConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, REGISTER_URL

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class ConfigFlow(HAConfigFlow, domain=DOMAIN):
    """Handle a config flow for WWS."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the login step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with DynamiT(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    session=async_get_clientsession(self.hass),
                    api_name="WWS",
                ) as client:
                    await client.async_login()
            except EdAuthError:
                errors["base"] = "invalid_auth"
            except EdError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="WestfalenWIND Ökostrom smart", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
            description_placeholders={"register_url": REGISTER_URL},
        )
