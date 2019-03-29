"""Config flow to configure Heos."""
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN


def format_title(host: str) -> str:
    """Format the title for config entries."""
    return "Controller ({})".format(host)


@config_entries.HANDLERS.register(DOMAIN)
class HeosFlowHandler(config_entries.ConfigFlow):
    """Define a flow for HEOS."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, user_input=None):
        """Occurs when an entry is setup through config."""
        host = user_input[CONF_HOST]
        return self.async_create_entry(
            title=format_title(host),
            data={CONF_HOST: host})
