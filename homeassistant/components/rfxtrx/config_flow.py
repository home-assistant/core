"""Config flow for RFXCOM RFXtrx integration."""
import logging

from homeassistant import config_entries

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for RFXCOM RFXtrx."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(import_config)
        return self.async_create_entry(title="RFXTRX", data=import_config)
