"""SFR Box config flow."""
from __future__ import annotations

from sfrbox_api.bridge import SFRBox
from sfrbox_api.exceptions import SFRBoxAuthenticationError, SFRBoxError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.httpx_client import get_async_client

from .const import DEFAULT_HOST, DEFAULT_USERNAME, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default=DEFAULT_HOST): selector.TextSelector(),
        vol.Optional(CONF_USERNAME, default=DEFAULT_USERNAME): selector.TextSelector(),
        vol.Optional(CONF_PASSWORD): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)
        ),
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
            box = SFRBox(ip=user_input[CONF_HOST], client=get_async_client(self.hass))
            try:
                system_info = await box.system_get_info()
                if (username := user_input.get(CONF_USERNAME)) and (
                    password := user_input.get(CONF_PASSWORD)
                ):
                    await box.authenticate(username=username, password=password)
            except SFRBoxAuthenticationError:
                errors["base"] = "invalid_auth"
            except SFRBoxError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(system_info.mac_addr)
                self._abort_if_unique_id_configured()
                self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
                return self.async_create_entry(title="SFR Box", data=user_input)

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input or {})
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
