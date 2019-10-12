"""Config flow to configure Philips Hue."""
import asyncio
import pprint

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST

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

    def __init__(self):
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if user_input is not None:
            self.host = self.context[CONF_HOST] = user_input[CONF_HOST]
            return await self._entry_from_bridge(self.host)
        hosts = configured_hosts(self.hass)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({vol.Required(CONF_HOST): vol.In(hosts)}),
        )

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry."""
        LOGGER.debug("async_step_import - %s" % pprint.pformat(import_info))
        host = self.context[CONF_HOST] = import_info[CONF_HOST]
        return await self._entry_from_bridge(host)

    async def _entry_from_bridge(self, host):
        """Return a config entry from an initialized bridge."""
        LOGGER.debug("entry_from_bridge - %s" % pprint.pformat(host))
        # Remove all other entries of hubs with same ID or host

        same_hub_entries = [
            entry.entry_id
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data[CONF_HOST] == host
        ]

        LOGGER.debug(
            "entry_from_bridge same_hub - %s" % pprint.pformat(same_hub_entries)
        )

        if same_hub_entries:
            await asyncio.wait(
                [
                    self.hass.config_entries.async_remove(entry_id)
                    for entry_id in same_hub_entries
                ]
            )

        return self.async_create_entry(title=host, data={CONF_HOST: host})
