"""Config flow for Eufy RoboVac."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_ID, CONF_MODEL, CONF_NAME
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_LOCAL_KEY, DOMAIN
from .model_mappings import MODEL_MAPPINGS

DEFAULT_MODEL = "T2253"

USER_STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="Eufy RoboVac"): str,
        vol.Required(CONF_MODEL, default=DEFAULT_MODEL): vol.In(
            sorted(MODEL_MAPPINGS)
        ),
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_ID): str,
        vol.Required(CONF_LOCAL_KEY): str,
    }
)


class EufyRoboVacConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eufy RoboVac."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the user step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=USER_STEP_DATA_SCHEMA
            )

        unique_id = user_input[CONF_ID]
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data=user_input,
        )
