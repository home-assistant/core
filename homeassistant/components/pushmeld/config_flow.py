# homeassistant/components/pushmeld/config_flow.py
"""Config flow for PushMeld."""

from typing import Any, override

import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.util import slugify

from .const import CONF_MAXCODE, DOMAIN

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_MAXCODE)): str,
        # Name is the local notification service name for this integration.
        # pylint: disable-next=home-assistant-config-flow-name-field
        probatio.Required(CONF_NAME): str,
    }
)


class PushMeldConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the PushMeld config flow."""

    VERSION = 1

    def _service_name_is_taken(self, name: str) -> bool:
        """Return whether the normalized local service name is already in use."""
        service_name = slugify(name)
        return any(
            slugify(entry.data.get(CONF_NAME, entry.title)) == service_name
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        )

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            maxcode = str(user_input[CONF_MAXCODE]).strip()
            name = str(user_input[CONF_NAME]).strip()

            if not maxcode:
                errors[CONF_MAXCODE] = "invalid_maxcode"
            elif not name:
                errors[CONF_NAME] = "invalid_name"
            elif self._service_name_is_taken(name):
                errors[CONF_NAME] = "name_exists"
            else:
                await self.async_set_unique_id(slugify(name))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={CONF_MAXCODE: maxcode, CONF_NAME: name},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
