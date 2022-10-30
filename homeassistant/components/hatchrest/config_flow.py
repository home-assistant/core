"""Discovery config flow for Hatch Rest device."""
import logging

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_ADDRESS
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HatchRestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Bluetooth discovery config flow for Hatch Rest devices."""

    VERSION = 1

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle bluetooth discovery."""
        _LOGGER.debug("Discovered hatch device: %s", discovery_info)
        await self.async_set_unique_id(format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=discovery_info.name,
            data={CONF_ADDRESS: discovery_info.address},
        )
