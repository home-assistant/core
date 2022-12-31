"""SFR Box config flow."""
from __future__ import annotations

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.httpx_client import get_async_client

from .const import DEFAULT_HOST, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
    }
)


class SFRBoxFlowHandler(ConfigFlow, domain=DOMAIN):
    """SFR Box config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                box = SFRBox(
                    ip=user_input[CONF_HOST],
                    client=get_async_client(self.hass),
                )
                system_info = await box.system_get_info()
            except SFRBoxError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(system_info.mac_addr)
                self._abort_if_unique_id_configured()
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title="SFR Box", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )
