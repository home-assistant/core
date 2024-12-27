"""Config flow for InfluxDB integration."""
import logging

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for InfluxDB."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_import(self, import_config=None) -> FlowResult:
        """Handle the initial step."""
        host = import_config.get("host")

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(import_config)

        return self.async_create_entry(title=host, data=import_config)
