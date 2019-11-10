"""Config flow for Hisense AEH-W4A1 integration."""
import logging

from pyaehw4a1.aehw4a1 import AehW4a1

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN
from . import CONF_IP_ADDRESS

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class AWSFlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        if self._async_current_entries():
            _LOGGER.warning("Only one configuration of Hisense AEH-W4A1 is allowed.")
            return self.async_abort(reason="single_instance_allowed")

        if import_config is not None:
            devices = import_config[CONF_IP_ADDRESS]
            for device in devices:
                try:
                    await AehW4a1(device).check()
                except ConnectionError:
                    _LOGGER.warning("Unreachable device at %s", self._unique_id)
                    return self.async_abort(reason="no_devices_found")


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    aehw4a1_ip_addresses = await AehW4a1().discovery()
    return len(aehw4a1_ip_addresses) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Hisense AEH-W4A1", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
