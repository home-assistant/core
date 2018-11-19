"""Config flow for UPNP."""
import logging
from collections import OrderedDict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant import data_entry_flow
from homeassistant.util import get_local_ip

from .const import (
    CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS,
    CONF_SSDP_DESCRIPTION, CONF_UDN
)
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)


async def async_ensure_domain_data(hass):
    """Ensure hass.data is filled properly."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN]['devices'] = hass.data[DOMAIN].get('devices', {})
    hass.data[DOMAIN]['discovered'] = hass.data[DOMAIN].get('discovered', {})
    hass.data[DOMAIN]['auto_config'] = hass.data[DOMAIN].get('auto_config', {
        'active': False,
        'enable_sensors': False,
        'enable_port_mapping': False,
        'ports': {'hass': 'hass'},
    })
    if 'local_ip' not in hass.data[DOMAIN]:
        hass.data[DOMAIN]['local_ip'] = \
            await hass.async_add_executor_job(get_local_ip)


@config_entries.HANDLERS.register(DOMAIN)
class UpnpFlowHandler(data_entry_flow.FlowHandler):
    """Handle a UPnP/IGD config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @property
    def _configured_upnp_igds(self):
        """Get all configured IGDs."""
        return {
            entry.data[CONF_UDN]: {
                'udn': entry.data[CONF_UDN],
            }
            for entry in self.hass.config_entries.async_entries(DOMAIN)
        }

    @property
    def _discovered_upnp_igds(self):
        """Get all discovered entries."""
        return self.hass.data[DOMAIN]['discovered']

    def _store_discovery_info(self, discovery_info):
        """Add discovery info."""
        udn = discovery_info['udn']
        self.hass.data[DOMAIN]['discovered'][udn] = discovery_info

    def _auto_config_settings(self):
        """Check if auto_config has been enabled."""
        return self.hass.data[DOMAIN]['auto_config']

    async def async_step_discovery(self, discovery_info):
        """
        Handle a discovered UPnP/IGD.

        This flow is triggered by the discovery component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        await async_ensure_domain_data(self.hass)

        if not discovery_info.get('udn') or not discovery_info.get('host'):
            # Silently ignore incomplete/broken devices to prevent constant
            # errors/warnings
            _LOGGER.debug('UPnP device is missing the udn. Provided info: %r',
                          discovery_info)
            return self.async_abort(reason='incomplete_device')

        # store discovered device
        discovery_info['friendly_name'] = discovery_info.get('host', '')

        # add name if available
        if discovery_info.get('name'):
            discovery_info['friendly_name'] += ' ({name})'.format(
                **discovery_info)

        self._store_discovery_info(discovery_info)

        # ensure not already discovered/configured
        if discovery_info.get('udn') in self._configured_upnp_igds:
            return self.async_abort(reason='already_configured')

        # auto config?
        auto_config = self._auto_config_settings()
        if auto_config['active']:
            import_info = {
                'name': discovery_info['friendly_name'],
                'enable_sensors': auto_config['enable_sensors'],
                'enable_port_mapping': auto_config['enable_port_mapping'],
            }

            return await self._async_save_entry(import_info)

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manual set up."""
        await async_ensure_domain_data(self.hass)

        # if user input given, handle it
        user_input = user_input or {}
        if 'name' in user_input:
            if not user_input['enable_sensors'] and \
               not user_input['enable_port_mapping']:
                return self.async_abort(reason='no_sensors_or_port_mapping')

            # ensure not already configured
            configured_names = [
                entry['friendly_name']
                for udn, entry in self._discovered_upnp_igds.items()
                if udn in self._configured_upnp_igds
            ]
            if user_input['name'] in configured_names:
                return self.async_abort(reason='already_configured')

            return await self._async_save_entry(user_input)

        # let user choose from all discovered, non-configured, UPnP/IGDs
        names = [
            entry['friendly_name']
            for udn, entry in self._discovered_upnp_igds.items()
            if udn not in self._configured_upnp_igds
        ]
        if not names:
            return self.async_abort(reason='no_devices_discovered')

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema(
                OrderedDict([
                    (vol.Required('name'), vol.In(names)),
                    (vol.Optional('enable_sensors', default=False), bool),
                    (vol.Optional('enable_port_mapping', default=False), bool),
                ])
            ))

    async def async_step_import(self, import_info):
        """Import a new UPnP/IGD as a config entry."""
        await async_ensure_domain_data(self.hass)

        return await self._async_save_entry(import_info)

    async def _async_save_entry(self, import_info):
        """Store UPNP/IGD as new entry."""
        await async_ensure_domain_data(self.hass)

        # ensure we know the host
        name = import_info['name']
        discovery_infos = [info
                           for info in self._discovered_upnp_igds.values()
                           if info['friendly_name'] == name]
        if not discovery_infos:
            return self.async_abort(reason='host_not_found')
        discovery_info = discovery_infos[0]

        return self.async_create_entry(
            title=discovery_info['name'],
            data={
                CONF_SSDP_DESCRIPTION: discovery_info['ssdp_description'],
                CONF_UDN: discovery_info['udn'],
                CONF_ENABLE_SENSORS: import_info['enable_sensors'],
                CONF_ENABLE_PORT_MAPPING: import_info['enable_port_mapping'],
            },
        )
