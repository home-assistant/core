"""Options flow for WatchYourLAN integration."""

import voluptuous as vol

from homeassistant import config_entries


class WatchYourLANOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle WatchYourLAN options."""

    def __init__(self, config_entry):
        """Initialize WatchYourLAN options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options for WatchYourLAN."""
        if user_input is not None:
            # Save the options
            return self.async_create_entry(title="", data=user_input)

        # Set up the options schema to allow users to modify the update interval
        options_schema = vol.Schema(
            {
                vol.Optional(
                    "update_interval",
                    default=self.config_entry.options.get("update_interval", 5),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60))
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)
