"""Config flow for OMIE - Spain and Portugal electricity prices integration."""

from typing import Any, Final

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import DOMAIN

DEFAULT_NAME: Final = "OMIE"


class OMIEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OMIE config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the first and only step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title=DEFAULT_NAME, data={})

        return self.async_show_form(step_id="user")
