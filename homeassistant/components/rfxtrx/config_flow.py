"""Config flow for RFXCOM RFXtrx integration."""
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT

from . import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


def _get_key(config):
    if CONF_PORT in config:
        return config[CONF_HOST], config[CONF_PORT]
    return config[CONF_DEVICE]


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFXCOM RFXtrx."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""

        import_key = _get_key(import_config)
        entries = self.hass.config_entries.async_entries(DOMAIN)
        for entry in entries:
            if _get_key(entry.data) == import_key:
                if entry.data != import_config:
                    self.hass.config_entries.async_update_entry(
                        entry, data=import_config
                    )
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(title="RFXTRX", data=import_config)
