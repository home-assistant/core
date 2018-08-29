"""Config flow for IGD."""
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback

import voluptuous as vol

from .const import DOMAIN
from .const import LOGGER as _LOGGER

@callback
def configured_udns(hass):
    """Get all configured UDNs."""
    return [
        entry.data['udn']
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]


@config_entries.HANDLERS.register(DOMAIN)
class IgdFlowHandler(data_entry_flow.FlowHandler):
    """Handle a Hue config flow."""

    VERSION = 1

    def __init__(self):
        """Initializer."""
        pass

    @property
    def _discovereds(self):
        """Get all discovered entries."""
        if DOMAIN not in self.hass.data:
            _LOGGER.debug('DOMAIN not in hass.data')
        if 'discovered' not in self.hass.data.get(DOMAIN, {}):
            _LOGGER.debug('discovered not in hass.data[DOMAIN]')

        return self.hass.data.get(DOMAIN, {}).get('discovered', {})

    def _store_discovery_info(self, discovery_info):
        """Add discovery info."""
        udn = discovery_info['udn']
        if DOMAIN not in self.hass.data:
            _LOGGER.debug('DOMAIN not in hass.data')
        self.hass.data[DOMAIN] = self.hass.data.get(DOMAIN, {})
        if 'discovered' not in self.hass.data[DOMAIN]:
            _LOGGER.debug('Creating new discovered: %s', self.hass.data[DOMAIN])
        self.hass.data[DOMAIN]['discovered'] = self.hass.data[DOMAIN].get('discovered', {})
        self.hass.data[DOMAIN]['discovered'][udn] = discovery_info

    async def async_step_discovery(self, discovery_info):
        """
        Handle a discovered IGD.

        This flow is triggered by the discovery component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        _LOGGER.debug('async_step_discovery %s: %s', id(self), discovery_info)

        # ensure not already discovered/configured
        udn = discovery_info['udn']
        if udn in configured_udns(self.hass):
            _LOGGER.debug('Already configured: %s', discovery_info)
            return self.async_abort(reason='already_configured')

        # store discovered device
        self._store_discovery_info(discovery_info)

        # abort --> not showing up in discovered things
        # return self.async_abort(reason='user_input_required')

        # user -> showing up in discovered things
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manual set up."""
        _LOGGER.debug('async_step_user %s: %s', id(self), user_input)

        # if user input given, handle it
        user_input = user_input or {}
        if 'igd_host' in user_input:
            if not user_input['sensors'] and not user_input['port_forward']:
                _LOGGER.debug('Aborting, no sensors and no portforward')
                return self.async_abort(reason='no_sensors_or_port_forward')

            configured_hosts = [
                entry['host']
                for entry in self._discovereds.values()
                if entry['udn'] in configured_udns(self.hass)
            ]
            if user_input['igd_host'] in configured_hosts:
                return self.async_abort(reason='already_configured')

            return await self._async_save(user_input)

        # let user choose from all discovered IGDs
        _LOGGER.debug('Discovered devices: %s', self._discovereds)
        igd_hosts = [
            entry['host']
            for entry in self._discovereds.values()
            if entry['udn'] not in configured_udns(self.hass)
        ]
        if not igd_hosts:
            return self.async_abort(reason='no_devices_discovered')

        return self.async_show_form(
            step_id='user',
            data_schema=vol.Schema({
                vol.Required('igd_host'): vol.In(igd_hosts),
                vol.Required('sensors'): bool,
                vol.Required('port_forward'): bool,
            })
        )

    async def _async_save(self, import_info):
        """Store IGD as new entry."""
        _LOGGER.debug('async_step_import %s: %s', id(self), import_info)

        # ensure we know the host
        igd_host = import_info['igd_host']
        discovery_infos = [info
                           for info in self._discovereds.values()
                           if info['host'] == igd_host]
        if not discovery_infos:
            return self.async_abort(reason='host_not_found')
        discovery_info = discovery_infos[0]

        return self.async_create_entry(
            title=discovery_info['name'],
            data={
                'ssdp_description': discovery_info['ssdp_description'],
                'udn': discovery_info['udn'],
                'sensors': import_info['sensors'],
                'port_forward': import_info['port_forward'],
            },
        )
