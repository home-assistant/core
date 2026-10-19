"""Config flow for the Helty Flow Cloud integration."""

from typing import Any, override

import probatio
from pyheltycloud import HeltyCloud, HeltyCloudAuthError, HeltyCloudError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class HeltyCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Helty Flow Cloud."""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = HeltyCloud(
                user_input[CONF_EMAIL],
                user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.login()
            except HeltyCloudAuthError:
                errors["base"] = "invalid_auth"
            except HeltyCloudError:
                errors["base"] = "cannot_connect"
            else:
                # The email is only a login alias of the account and can
                # change; the Cognito subject cannot.
                await self.async_set_unique_id(client.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
