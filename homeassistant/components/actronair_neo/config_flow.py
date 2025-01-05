"""Setup config flow for Actron Neo integration."""

import logging

from actron_neo_api import ActronNeoAPI, ActronNeoAPIError, ActronNeoAuthError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import DOMAIN, ERROR_API_ERROR, ERROR_INVALID_AUTH, ERROR_NO_SYSTEMS_FOUND

_LOGGER = logging.getLogger(__name__)


class ActronNeoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Actron Air Neo."""

    VERSION = 3

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.api = None
        self.ac_systems = None

    async def async_step_user(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
                errors=errors,
            )

        if not user_input.get("username") or not user_input.get("password"):
            errors["base"] = ERROR_INVALID_AUTH
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
                errors=errors,
            )

        _LOGGER.debug("Connecting to Actron Neo API")
        try:
            self.api = ActronNeoAPI(
                username=user_input["username"], password=user_input["password"]
            )
        except ActronNeoAuthError:
            errors["base"] = ERROR_INVALID_AUTH
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
                errors=errors,
            )

        if self.api is None:
            errors["base"] = ERROR_API_ERROR
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("username"): str,
                        vol.Required("password"): str,
                    }
                ),
                errors=errors,
            )

        try:
            await self.api.request_pairing_token("HomeAssistant", "ha-instance-id")
            await self.api.refresh_token()
        except ActronNeoAPIError:
            errors["base"] = ERROR_API_ERROR

        systems = await self.api.get_ac_systems()
        self.ac_systems = systems.get("_embedded", {}).get("ac-system", [])
        if not self.ac_systems:
            errors["base"] = ERROR_NO_SYSTEMS_FOUND

        if len(self.ac_systems) > 1:
            return self.async_show_form(
                step_id="select_system",
                data_schema=vol.Schema(
                    {
                        vol.Required("selected_system"): vol.In(
                            {
                                system["serial"]: system["description"]
                                for system in self.ac_systems
                            }
                        )
                    }
                ),
            )

        selected_system = self.ac_systems[0]

        serial_number = selected_system["serial"]
        await self.async_set_unique_id(serial_number)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=selected_system["description"],
            data={
                "pairing_token": self.api.pairing_token,
                "serial_number": serial_number,
            },
        )

    async def async_step_select_system(
        self, user_input=None
    ) -> config_entries.ConfigFlowResult:
        """Handle system selection step."""
        if not self.ac_systems:
            return self.async_abort(reason=ERROR_NO_SYSTEMS_FOUND)
        if not self.api.pairing_token:
            return self.async_abort(reason=ERROR_API_ERROR)
        selected_system = next(
            (
                system
                for system in self.ac_systems
                if system["serial"] == user_input["selected_system"]
            ),
            None,
        )
        if not selected_system:
            return self.async_abort(reason=ERROR_NO_SYSTEMS_FOUND)
        return self.async_create_entry(
            title=selected_system["description"],
            data={
                "pairing_token": self.api.pairing_token,
                "serial_number": selected_system["serial"],
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ActronNeoOptionsFlowHandler(config_entry)


class ActronNeoOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Actron Air Neo."""

    def __init__(self, config_entry) -> None:
        """Handle the initial setup."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({}),
        )
