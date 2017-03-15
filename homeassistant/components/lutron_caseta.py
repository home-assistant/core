import logging
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import (Entity, generate_entity_id)
from homeassistant.loader import get_component

REQUIREMENTS = ['https://github.com/gurumitts/pylutron-caseta/archive/0.1.0.zip#'
                'pylutron-caseta==0.1.0']

_LOGGER = logging.getLogger(__name__)

LUTRON_CASETA_SMARTBRIDGE = 'lutron_smartbridge'
LUTRON_CASETA_DEVICES = 'lutron_devices'

DOMAIN = 'lutron_caseta'

def setup(hass, base_config):
    """Setup the Lutron component."""
    from pylutron_caseta.smartbridge import Smartbridge

    hass.data[LUTRON_CASETA_SMARTBRIDGE] = None
    hass.data[LUTRON_CASETA_DEVICES] = None


    config = base_config.get(DOMAIN)
    hass.data[LUTRON_CASETA_SMARTBRIDGE] = Smartbridge(
        hostname=config['host'],
        username=config['user'],
        password=config['password']
    )
    caseta_devices = hass.data[LUTRON_CASETA_SMARTBRIDGE].get_devices()
    _LOGGER.error("Connected to Lutron smartbridge at %s", config['host'])

    # [Currently]Only supports lutron wall dimmers as hass lights
    # [Future] switches should be trivial to add
    components = {"light": [], "switch": []}

    for device in caseta_devices:
        # Lutron wall dimmers will be mapped as lights
        if device["type"] == "WallDimmer":
            components["light"].append(device)
        if device["type"] == "WallSwitch":
            components["switch"].append(device)
        # Need to support more Lutron devices but I don't have any more.

    hass.data[LUTRON_CASETA_DEVICES] = components
    _LOGGER.error(hass.data[LUTRON_CASETA_DEVICES])

    for component in components:
        if len(components[component]) > 0:
            discovery.load_platform(hass, component, DOMAIN, None, base_config)
    return True





    return True
