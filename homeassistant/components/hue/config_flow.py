"""Config flow to configure Philips Hue."""
import asyncio
import json
import os

import async_timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import aiohttp_client

from .bridge import get_bridge
from .const import DOMAIN, LOGGER
from .errors import AuthenticationRequired, CannotConnect


@callback
def configured_hosts(hass):
    """Return a set of the configured hosts."""
    return set(entry.data['host'] for entry
               in hass.config_entries.async_entries(DOMAIN))


def _find_username_from_config(hass, filename):
    """Load username from config.

    This was a legacy way of configuring Hue until Home Assistant 0.67.
    """
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        return None

    with open(path) as inp:
        try:
            return list(json.load(inp).values())[0]['username']
        except ValueError:
            # If we get invalid JSON
            return None


@config_entries.HANDLERS.register(DOMAIN)
class HueFlowHandler(config_entries.ConfigFlowHandler):
    """Handle a Hue config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Hue flow."""
        self.host = None

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        from aiohue.discovery import discover_nupnp

        if user_input is not None:
            self.host = user_input['host']
            return await self.async_step_link()

        websession = aiohttp_client.async_get_clientsession(self.hass)

        try:
            with async_timeout.timeout(5):
                bridges = await discover_nupnp(websession=websession)
        except asyncio.TimeoutError:
            return self.async_abort(
                reason='discover_timeout'
            )

        if not bridges:
            return self.async_abort(
                reason='no_bridges'
            )

        # Find already configured hosts
        configured = configured_hosts(self.hass)

        hosts = [bridge.host for bridge in bridges
                 if bridge.host not in configured]

        if not hosts:
            return self.async_abort(
                reason='all_configured'
            )

        elif len(hosts) == 1:
            self.host = hosts[0]
            return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            data_schema=vol.Schema({
                vol.Required('host'): vol.In(hosts)
            })
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Hue bridge.

        Given a configured host, will ask the user to press the link button
        to connect to the bridge.
        """
        errors = {}

        # We will always try linking in case the user has already pressed
        # the link button.
        try:
            bridge = await get_bridge(
                self.hass, self.host, username=None
            )

            return await self._entry_from_bridge(bridge)
        except AuthenticationRequired:
            errors['base'] = 'register_failed'

        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", self.host)
            errors['base'] = 'linking'

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception(
                'Unknown error connecting with Hue bridge at %s',
                self.host)
            errors['base'] = 'linking'

        # If there was no user input, do not show the errors.
        if user_input is None:
            errors = {}

        return self.async_show_form(
            step_id='link',
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info):
        """Handle a discovered Hue bridge.

        This flow is triggered by the discovery component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # Filter out emulated Hue
        if "HASS Bridge" in discovery_info.get('name', ''):
            return self.async_abort(reason='already_configured')

        host = discovery_info.get('host')

        if host in configured_hosts(self.hass):
            return self.async_abort(reason='already_configured')

        # This value is based off host/description.xml and is, weirdly, missing
        # 4 characters in the middle of the serial compared to results returned
        # from the NUPNP API or when querying the bridge API for bridgeid.
        # (on first gen Hue hub)
        serial = discovery_info.get('serial')

        return await self.async_step_import({
            'host': host,
            # This format is the legacy format that Hue used for discovery
            'path': 'phue-{}.conf'.format(serial)
        })

    async def async_step_import(self, import_info):
        """Import a new bridge as a config entry.

        Will read authentication from Phue config file if available.

        This flow is triggered by `async_setup` for both configured and
        discovered bridges. Triggered for any bridge that does not have a
        config entry yet (based on host).

        This flow is also triggered by `async_step_discovery`.

        If an existing config file is found, we will validate the credentials
        and create an entry. Otherwise we will delegate to `link` step which
        will ask user to link the bridge.
        """
        host = import_info['host']
        path = import_info.get('path')

        if path is not None:
            username = await self.hass.async_add_job(
                _find_username_from_config, self.hass,
                self.hass.config.path(path))
        else:
            username = None

        try:
            bridge = await get_bridge(
                self.hass, host, username
            )

            LOGGER.info('Imported authentication for %s from %s', host, path)

            return await self._entry_from_bridge(bridge)
        except AuthenticationRequired:
            self.host = host

            LOGGER.info('Invalid authentication for %s, requesting link.',
                        host)

            return await self.async_step_link()

        except CannotConnect:
            LOGGER.error("Error connecting to the Hue bridge at %s", host)
            return self.async_abort(reason='cannot_connect')

        except Exception:  # pylint: disable=broad-except
            LOGGER.exception('Unknown error connecting with Hue bridge at %s',
                             host)
            return self.async_abort(reason='unknown')

    async def _entry_from_bridge(self, bridge):
        """Return a config entry from an initialized bridge."""
        # Remove all other entries of hubs with same ID or host
        host = bridge.host
        bridge_id = bridge.config.bridgeid

        same_hub_entries = [entry.entry_id for entry
                            in self.hass.config_entries.async_entries(DOMAIN)
                            if entry.data['bridge_id'] == bridge_id or
                            entry.data['host'] == host]

        if same_hub_entries:
            await asyncio.wait([self.hass.config_entries.async_remove(entry_id)
                                for entry_id in same_hub_entries])

        return self.async_create_entry(
            title=bridge.config.name,
            data={
                'host': host,
                'bridge_id': bridge_id,
                'username': bridge.username,
            }
        )
