"""Setup dvsportal."""

import logging
from typing import Any

from dvsportal import DVSPortal, DVSPortalAuthError
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import AbortFlow

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional("user_agent"): str,
    }
)


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""


class DVSPortalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DVSPortal."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await self.validate_input(user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except AbortFlow:
                raise
            except Exception:  # pylint: disable=broad-except
                logging.exception("Error in async step user")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def validate_input(self, data: dict[str, Any]):
        """Validate the user input allows us to connect."""
        api_host = data[CONF_HOST]
        identifier = data[CONF_USERNAME]
        password = data[CONF_PASSWORD]
        user_agent = data.get("user_agent", "HomeAssistant")

        await self.async_set_unique_id(f"{api_host}.{identifier}")
        self._abort_if_unique_id_configured()

        try:
            async with DVSPortal(
                api_host=api_host,
                identifier=identifier,
                password=password,
                user_agent=user_agent,
            ) as dvs_portal:
                await dvs_portal.token()
        except DVSPortalAuthError:
            raise InvalidAuth from None

        return {"title": identifier}
