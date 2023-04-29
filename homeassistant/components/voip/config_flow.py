"""Config flow for VoIP integration."""
from __future__ import annotations

from typing import Any

from voip_utils import SIP_PORT
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_SIP_PORT, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(
            CONF_SIP_PORT,
            default=SIP_PORT,
        ): cv.port,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VoIP integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
            )

        return self.async_create_entry(
            title="Voice over IP",
            data=user_input,
        )
