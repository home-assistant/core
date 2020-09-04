"""Config flow for DSMR integration."""
import logging
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN  # pylint:disable=unused-import

_LOGGER = logging.getLogger(__name__)


class DSMRFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DSMR."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    def _abort_if_host_port_configured(
        self,
        port: str,
        host: str = None,
        updates: Optional[Dict[Any, Any]] = None,
        reload_on_update: bool = True,
    ):
        """Test if host and port are already configured."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_HOST) == host and entry.data[CONF_PORT] == port:
                if updates is not None:
                    changed = self.hass.config_entries.async_update_entry(
                        entry, data={**entry.data, **updates}
                    )
                    if (
                        changed
                        and reload_on_update
                        and entry.state
                        in (
                            config_entries.ENTRY_STATE_LOADED,
                            config_entries.ENTRY_STATE_SETUP_RETRY,
                        )
                    ):
                        self.hass.async_create_task(
                            self.hass.config_entries.async_reload(entry.entry_id)
                        )
                return self.async_abort(reason="already_configured")

        return None

    async def async_step_import(self, import_config=None):
        """Handle the initial step."""
        host = import_config.get(CONF_HOST)
        port = import_config[CONF_PORT]

        status = self._abort_if_host_port_configured(port, host, import_config)
        if status is not None:
            return status

        if host is not None:
            name = f"{host}:{port}"
        else:
            name = port

        return self.async_create_entry(title=name, data=import_config)
