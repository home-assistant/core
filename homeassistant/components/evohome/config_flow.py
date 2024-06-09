"""Config flow to configure Evohome integration."""

from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_SCAN_INTERVAL

from .const import DOMAIN


class EvoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Evohome."""

    VERSION = 1

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle a flow initiated by configuration file."""

        data = import_data.copy()

        scan_interval: timedelta = data.pop(CONF_SCAN_INTERVAL)
        data[CONF_SCAN_INTERVAL] = int(scan_interval.total_seconds())

        return self.async_create_entry(title="Evohome", data=data)
