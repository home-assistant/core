"""Config flow for the Helty Flow Cloud integration."""

from typing import Any, override

from pyheltycloud import HeltyCloud, HeltyCloudAuthError, HeltyCloudError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HeltyCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Helty Flow Cloud."""

    async def _async_validate(self, email: str, password: str) -> dict[str, str]:
        """Check the credentials, returning the errors to show, if any."""
        client = HeltyCloud(email, password, session=async_get_clientsession(self.hass))
        try:
            await client.get_devices()
        except HeltyCloudAuthError:
            return {"base": "invalid_auth"}
        except HeltyCloudError:
            return {"base": "cannot_connect"}
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            email = user_input[CONF_EMAIL]
            await self.async_set_unique_id(email.lower())
            self._abort_if_unique_id_configured()
            errors = await self._async_validate(email, user_input[CONF_PASSWORD])
            if not errors:
                return self.async_create_entry(title=email, data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
