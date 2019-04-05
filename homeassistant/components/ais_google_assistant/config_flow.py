"""Config flow to configure the AIS Spotify Service component."""

from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN
G_AUTH_URL = None


def setUrl(url):
    global G_AUTH_URL
    G_AUTH_URL = url

@callback
def configured_service(hass):
    """Return a set of the configured hosts."""
    return set('spotify' for entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class AisGoogleAssistantFlowHandler(config_entries.ConfigFlow):
    """Spotify config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize zone configuration flow."""
        pass

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        if self._async_current_entries():
            return self.async_abort(reason='single_instance_allowed')
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return await self.async_step_init(user_input=None)
        return self.async_show_form(
            step_id='confirm',
            errors=errors,
        )

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Dostęp do Servisu Asystent Google",
                data=user_input
            )

        return self.async_show_form(
            step_id='init',
            errors=errors,
            description_placeholders={
                'auth_url': G_AUTH_URL,
            },
        )



