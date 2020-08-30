"""Config flow for DSMR integration."""
import logging

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class DSMRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSMR."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""
        if CONF_HOST in import_config:
            name = f"{import_config[CONF_HOST]}:{import_config[CONF_PORT]}"
        else:
            name = import_config[CONF_PORT]

        await self.async_set_unique_id(name)
        self._abort_if_unique_id_configured(import_config)
        return self.async_create_entry(title=name, data=import_config)
