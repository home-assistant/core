"""Config flow for IGD."""
import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import callback

from .const import CONF_ENABLE_PORT_MAPPING, CONF_ENABLE_SENSORS
from .const import DOMAIN


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
        return self.hass.data.get(DOMAIN, {}).get('discovered', {})

    def _store_discovery_info(self, discovery_info):
        """Add discovery info."""
        udn = discovery_info['udn']
        self.hass.data[DOMAIN] = self.hass.data.get(DOMAIN, {})
        self.hass.data[DOMAIN]['discovered'] = \
            self.hass.data[DOMAIN].get('discovered', {})
        self.hass.data[DOMAIN]['discovered'][udn] = discovery_info

    def _auto_config_settings(self):
        """Check if auto_config has been enabled."""
        self.hass.data[DOMAIN] = self.hass.data.get(DOMAIN, {})
        return self.hass.data[DOMAIN].get('auto_config', {
            'active': False,
        })

    async def async_step_discovery(self, discovery_info):
        """
        Handle a discovered IGD.

        This flow is triggered by the discovery component. It will check if the
        host is already configured and delegate to the import step if not.
        """
        # ensure not already discovered/configured
        udn = discovery_info['udn']
        if udn in configured_udns(self.hass):
            return self.async_abort(reason='already_configured')

        # store discovered device
        self._store_discovery_info(discovery_info)

        # auto config?
        auto_config = self._auto_config_settings()
        if auto_config['active']:
            import_info = {
                'igd_host': discovery_info['host'],
                'sensors': auto_config['sensors'],
                'port_forward': auto_config['port_forward'],
            }

            return await self._async_save_entry(import_info)

        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Manual set up."""
        # if user input given, handle it
        user_input = user_input or {}
        if 'igd_host' in user_input:
            if not user_input['sensors'] and not user_input['port_forward']:
                return self.async_abort(reason='no_sensors_or_port_forward')

            configured_hosts = [
                entry['host']
                for entry in self._discovereds.values()
                if entry['udn'] in configured_udns(self.hass)
            ]
            if user_input['igd_host'] in configured_hosts:
                return self.async_abort(reason='already_configured')

            return await self._async_save_entry(user_input)

        # let user choose from all discovered IGDs
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

    async def async_step_import(self, import_info):
        """Import a new IGD as a config entry."""
        return await self._async_save_entry(import_info)

    async def _async_save_entry(self, import_info):
        """Store IGD as new entry."""
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
                CONF_ENABLE_SENSORS: import_info['sensors'],
                CONF_ENABLE_PORT_MAPPING: import_info['port_forward'],
            },
        )
