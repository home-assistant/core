"""Config flow to configure Evohome integration."""

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RamsesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Evohome."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        scan_interval: timedelta = import_data.pop(CONF_SCAN_INTERVAL)
        import_data[CONF_SCAN_INTERVAL] = int(scan_interval.total_seconds())

        return self.async_create_entry(title="Evohome", data=import_data)
