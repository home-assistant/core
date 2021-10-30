"""Config flows for greeneye_monitor."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_PORT
from homeassistant.helpers.typing import DiscoveryInfoType

from .const import CONF_MONITORS, DOMAIN


class GreeneyeMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for greeneye_monitor."""

    async def async_step_import(
        self, discovery_info: DiscoveryInfoType
    ) -> data_entry_flow.FlowResult:
        """Create a config entry from YAML configuration."""
        data = {CONF_PORT: discovery_info[CONF_PORT]}
        options = {CONF_MONITORS: discovery_info[CONF_MONITORS]}
        if entry := await self.async_set_unique_id(DOMAIN):
            self.hass.config_entries.async_update_entry(
                entry, data=data, options=options
            )
            self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="GreenEye Monitor", data=data, options=options
        )
