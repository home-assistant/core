"""Config flow to configure the Arcam FMJ component."""
from operator import itemgetter

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN

_GETKEY = itemgetter(CONF_HOST, CONF_PORT)


@config_entries.HANDLERS.register(DOMAIN)
class ArcamFmjFlowHandler(config_entries.ConfigFlow):
    """Handle a SimpliSafe config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        entries = self.hass.config_entries.async_entries(DOMAIN)
        import_key = _GETKEY(import_config)
        for entry in entries:
            if _GETKEY(entry.data) == import_key:
                return self.async_abort(reason="already_setup")

        return self.async_create_entry(title="Arcam FMJ", data=import_config)
