"""Config flow for Garages Amsterdam integration."""
import voluptuous as vol

from homeassistant import config_entries

from . import get_coordinator
from .const import DOMAIN  # pylint:disable=unused-import


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Garages Amsterdam."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    _options = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if self._options is None:
            self._options = {}
            coordinator = await get_coordinator(self.hass)
            for case in sorted(
                coordinator.data.values(), key=lambda case: case.garageName
            ):
                self._options[case.garageName] = case.garageName

        if user_input is not None:
            await self.async_set_unique_id(user_input["garageName"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._options[user_input["garageName"]], data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required("garageName"): vol.In(self._options)}),
            errors=errors,
        )
