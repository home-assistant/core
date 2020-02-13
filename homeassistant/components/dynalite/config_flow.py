"""Config flow to configure Dynalite hub."""
from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .const import DOMAIN, LOGGER  # pylint: disable=unused-import


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    # pylint: disable=no-member # https://github.com/PyCQA/pylint/issues/3167

    def __init__(self):
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry."""
        LOGGER.debug("async_step_import - %s", import_info)
        host = self.context[CONF_HOST] = import_info[CONF_HOST]
        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured()
        return await self._entry_from_bridge(host)

    async def _entry_from_bridge(self, host):
        """Return a config entry from an initialized bridge."""
        LOGGER.debug("entry_from_bridge - %s", host)

        return self.async_create_entry(title=host, data={CONF_HOST: host})
