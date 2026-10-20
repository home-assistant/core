# homeassistant/components/pushmeld/config_flow.py
"""Config flow for PushMeld."""

from typing import Any, override

import probatio

from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.util import slugify

from .const import CONF_MAXCODE, DEFAULT_NAME, DOMAIN

USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_MAXCODE)): str,
    }
)


class PushMeldConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the PushMeld config flow."""

    VERSION = 1

    def _get_entry_title(self) -> str:
        """Return an available default config-entry title."""
        index = 1
        while True:
            title = DEFAULT_NAME if index == 1 else f"{DEFAULT_NAME} {index}"
            service_name = slugify(title)
            if not self.hass.services.has_service(
                NOTIFY_DOMAIN, service_name
            ) and not any(
                slugify(entry.title) == service_name
                for entry in self.hass.config_entries.async_entries(DOMAIN)
            ):
                return title
            index += 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            maxcode = str(user_input[CONF_MAXCODE]).strip()

            if not maxcode:
                errors[CONF_MAXCODE] = "invalid_maxcode"
            else:
                self._async_abort_entries_match({CONF_MAXCODE: maxcode})
                return self.async_create_entry(
                    title=self._get_entry_title(),
                    data={CONF_MAXCODE: maxcode},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )
