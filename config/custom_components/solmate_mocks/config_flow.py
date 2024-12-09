"""Config flow for Solmate Mocks."""

from homeassistant import config_entries


class ConfigFlow(config_entries.ConfigFlow, domain="solmate_mocks"):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_import(self, import_info):
        """Set up this integration using yaml."""
        return self.async_create_entry(title="Solmate Mocks", data={})

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return self.async_create_entry(title="Solmate Mocks", data={})
