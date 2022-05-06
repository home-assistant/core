"""Config flow for Feedreader integration."""
import voluptuous as vol

from homeassistant import config_entries

from . import (
    CONF_MAX_ENTRIES,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    DEFAULT_MAX_ENTRIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class FeedreaderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Feedreader integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle single step config flow here."""

        if user_input is not None:
            return self.async_create_entry(
                title=f"Feedreader: {user_input[CONF_URL]}", data=user_input
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_URL): str,
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL.seconds
                ): int,
                vol.Optional(CONF_MAX_ENTRIES, default=DEFAULT_MAX_ENTRIES): int,
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)
