"""Config flow for IoTMeter integration."""

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN


class EVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IoTMeter."""

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            ip_address = user_input.get("ip_address")
            port = user_input.get("port")

            if ip_address and port:
                return self.async_create_entry(title="IoTMeter", data=user_input)
            errors["base"] = "invalid_input"

        data_schema = vol.Schema(
            {vol.Required("ip_address"): str, vol.Optional("port", default=8000): int}
        )

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle the reconfiguration step."""
        errors = {}
        # Get the current configuration from config_entry
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        current_ip = config_entry.data.get("ip_address", "")
        current_port = config_entry.data.get("port", 8000)

        if user_input is not None:
            ip_address = user_input.get("ip_address")
            port = user_input.get("port")

            if ip_address and port:
                # Update the config_entry with new data
                self.hass.config_entries.async_update_entry(
                    config_entry, data=user_input
                )
                return self.async_abort(reason="reconfigured")
            errors["base"] = "invalid_input"

        data_schema = vol.Schema(
            {
                vol.Required("ip_address", default=current_ip): str,
                vol.Optional("port", default=current_port): int,
            }
        )

        return self.async_show_form(
            step_id="reconfigure", data_schema=data_schema, errors=errors
        )
