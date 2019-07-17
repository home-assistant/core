import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import slugify

from .const import DOMAIN


@callback
def velbus_entries(hass: HomeAssistant):
    """Return configurations of SMHI component."""
    return set((slugify(entry.data[CONF_NAME])) for
       entry in hass.config_entries.async_entries(DOMAIN))


class VelbusConfigFlow(config_entries.ConfigFlow):

    def __init__(self) -> None:
        self._errors = {}

    def _name_in_configuration_exists(self, name: str) -> bool:
        """Return True if name exists in configuration."""
        if name in velbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Step when user intializes a integration"""
        self._errors = {}
        print("=====")
        print(user_input)
        print("=====")
        if user_input is not None:
            name = slugify(user_input[CONF_NAME])
            if not self._name_in_configuration_exists(name):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )
            else:
                self._errors[CONF_NAME] = 'name_exists'

        print("=====")
        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_DEVICE): str
            }),
            errors=self._errors
        )
