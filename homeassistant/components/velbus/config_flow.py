import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def velbus_entries(hass: HomeAssistant):
    """Return configurations of SMHI component."""
    return set((slugify(entry.data[CONF_NAME])) for
       entry in hass.config_entries.async_entries(DOMAIN))


@config_entries.HANDLERS.register(DOMAIN)
class VelbusConfigFlow(config_entries.ConfigFlow):

    def __init__(self) -> None:
        self._errors = {}


    async def _create_device(self, name: str, prt: str):
        return self.async_create_entry(
            title=name,
            data={
                CONF_PORT: prt
            }
        )

    def _name_in_configuration_exists(self, name: str) -> bool:
        """Return True if name exists in configuration."""
        if name in velbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user intializes a integration"""
        self._errors = {}
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            if not self._name_in_configuration_exists(name):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            else:
                self._errors[CONF_NAME] = 'name_exists'

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_PORT): str
            }),
            errors=self._errors
        )

    async def async_step_import(self, user_input=None):
        """Import a config entry."""
        prt = user_input.get(CONF_PORT)
        name = user_input.get(CONF_NAME)
        if not prt:
            return await self.async_step_user()
        return await self._create_device(name, prt)

