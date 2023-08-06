"""Config flow for Mullvad VPN integration."""
from mullvad_api import MullvadAPI, MullvadAPIError

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Mullvad VPN."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        self._async_abort_entries_match()

        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(MullvadAPI)
            except MullvadAPIError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title="Mullvad VPN", data=user_input)

        return self.async_show_form(step_id="user", errors=errors)
