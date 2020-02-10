"""Config flow to configure Dynalite hub."""
import asyncio

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .const import DOMAIN, LOGGER


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    )


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
        return await self._entry_from_bridge(host)

    async def _entry_from_bridge(self, host):
        """Return a config entry from an initialized bridge."""
        LOGGER.debug("entry_from_bridge - %s", host)
        # Remove all other entries of hubs with same ID or host

        same_hub_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_HOST] == host
        ]

        LOGGER.debug("entry_from_bridge same_hub - %s", same_hub_entries)

        if same_hub_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_hub_entries
                ]
            )

        return self.async_create_entry(title=host, data={CONF_HOST: host})
