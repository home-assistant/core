"""
Support for Vanderbilt (formerly Siemens) SPC alarm systems.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/spc/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers import discovery, aiohttp_client
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyspcwebgw==0.4.0']

_LOGGER = logging.getLogger(__name__)

ATTR_DISCOVER_DEVICES = 'devices'
ATTR_DISCOVER_AREAS = 'areas'

CONF_WS_URL = 'ws_url'
CONF_API_URL = 'api_url'

DATA_REGISTRY = 'spc_registry'
DATA_API = 'spc_api'
DOMAIN = 'spc'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_WS_URL): cv.string,
        vol.Required(CONF_API_URL): cv.string
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up the SPC component."""
    from pyspcwebgw import SpcWebGateway

    registry = SpcRegistry()
    hass.data[DATA_REGISTRY] = registry

    @callback
    async def async_upate_callback(entity):
        from pyspcwebgw.area import Area
        from pyspcwebgw.zone import Zone

        if isinstance(entity, Area):
            device = registry.get_alarm_device(entity.id)
        elif isinstance(entity, Zone):
            device = registry.get_sensor_device(entity.id)
        if device:
            device.async_schedule_update_ha_state()

    session = aiohttp_client.async_get_clientsession(hass)

    spc = SpcWebGateway(loop=hass.loop, session=session,
                        api_url=config[DOMAIN].get(CONF_API_URL),
                        ws_url=config[DOMAIN].get(CONF_WS_URL),
                        async_callback=async_upate_callback)

    hass.data[DATA_API] = spc

    if not await spc.async_load_parameters():
        _LOGGER.error('Failed to load area/zone information from SPC.')
        return False

    # add sensor devices for each zone (typically motion/fire/door sensors)
    hass.async_create_task(discovery.async_load_platform(
        hass, 'binary_sensor', DOMAIN,
        {ATTR_DISCOVER_DEVICES: spc.zones.values()}, config))

    # create a separate alarm panel for each area
    hass.async_create_task(discovery.async_load_platform(
        hass, 'alarm_control_panel', DOMAIN,
        {ATTR_DISCOVER_AREAS: spc.areas.values()}, config))

    # start listening for incoming events over websocket
    spc.start()

    return True


class SpcRegistry:
    """Maintain mappings between SPC zones/areas and HA entities."""

    def __init__(self):
        """Initialize the registry."""
        self._zone_id_to_sensor_map = {}
        self._area_id_to_alarm_map = {}

    def register_sensor_device(self, zone_id, device):
        """Add a sensor device to the registry."""
        self._zone_id_to_sensor_map[zone_id] = device

    def get_sensor_device(self, zone_id):
        """Retrieve a sensor device for a specific zone."""
        return self._zone_id_to_sensor_map.get(zone_id, None)

    def register_alarm_device(self, area_id, device):
        """Add an alarm device to the registry."""
        self._area_id_to_alarm_map[area_id] = device

    def get_alarm_device(self, area_id):
        """Retrieve an alarm device for a specific area."""
        return self._area_id_to_alarm_map.get(area_id, None)
