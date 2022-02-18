from homeassistant import config_entries
import voluptuous as vol
from .sensor import DOMAIN, CONF_SERIAL_PORT
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv


EDL_SCHEMA = vol.Schema(
    {vol.Required(CONF_SERIAL_PORT): cv.string, vol.Optional(CONF_NAME): cv.string}
)


class EDL21ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, info):
        if info is not None:
            self.data = info
            return self.async_create_entry(title="EDL21", data=self.data)

        return self.async_show_form(step_id="user", data_schema=EDL_SCHEMA)
