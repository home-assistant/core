"""Config flow to configure ShoppingList component."""
from homeassistant import config_entries

from .const import DOMAIN


class ShoppingListFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ShoppingList component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # Check if already configured
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(title="Shopping List", data=user_input)

        return self.async_show_form(step_id="user")

    async_step_import = async_step_user
