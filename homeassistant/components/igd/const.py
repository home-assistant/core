"""Constants for the IGD component."""
import logging


DOMAIN = 'igd'
LOGGER = logging.getLogger('homeassistant.components.igd')
CONF_ENABLE_PORT_MAPPING = 'port_forward'
CONF_ENABLE_SENSORS = 'sensors'
CONF_UDN = 'udn'
CONF_SSDP_DESCRIPTION = 'ssdp_description'


def ensure_domain_data(hass):
    """Ensure hass.data is filled properly."""
    hass.data[DOMAIN] = hass.data.get(DOMAIN, {})
    hass.data[DOMAIN]['devices'] = hass.data[DOMAIN].get('devices', {})
    hass.data[DOMAIN]['sensors'] = hass.data[DOMAIN].get('sensors', {})
    hass.data[DOMAIN]['discovered'] = hass.data[DOMAIN].get('discovered', {})
    hass.data[DOMAIN]['auto_config'] = hass.data[DOMAIN].get('auto_config', {
        'active': False,
        'port_forward': False,
        'sensors': False,
    })
