"""Config flow for Hello State."""

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

DOMAIN = "hello_state"


class HelloStateConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello State."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> ConfigFlowResult:
        """Handle the initial step initiated by the user."""
        return self.async_create_entry(title="Hello State", data={})
