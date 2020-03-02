"""Config flow to configure ShoppingList component."""
from homeassistant import config_entries

from .const import DOMAIN  # pylint: disable=unused-import


class ShoppingListFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for ShoppingList component."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH
    SHOPPING_LIST = "Shopping List"

    def __init__(self):
        """Init ShoppingListFlowHandler."""
        self._errors = {}

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        self._abort_if_unique_id_configured()

        self._errors = {}

        if user_input is not None:
            return self.async_create_entry(title=self.SHOPPING_LIST, data=user_input)

        return self.async_show_form(step_id="user", errors=self._errors)

    async def async_step_import(self, user_input):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        return self.async_create_entry(title="configuration.yaml", data={})
