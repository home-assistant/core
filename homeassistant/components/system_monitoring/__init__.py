"""
System monitoring component.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/system_monitoring/
"""
import asyncio
import logging

from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'system_monitoring'

ENTITY_ID_FORMAT = DOMAIN + '.{}'

CONF_SYSTEM = 'system'

SENSOR_TYPES = {
    'cpu_speed': ['CPU Speed', 'GHz', 'mdi:pulse'],
    'disk_free': ['Disk free', 'GiB', 'mdi:harddisk'],
    'disk_use': ['Disk used', 'GiB', 'mdi:harddisk'],
    'load_15m': ['Average load (15m)', '', 'mdi:memory'],
    'load_1m': ['Average load (1m)', '', 'mdi:memory'],
    'memory_free': ['Memory free', 'MiB', 'mdi:memory'],
    'memory_used': ['Memory used', 'MiB', 'mdi:memory'],
}


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the System monitoring component."""
    component = EntityComponent(_LOGGER, DOMAIN, hass)

    yield from component.async_setup(config)
    return True


# pylint: disable=no-member, no-self-use
class SystemMonitoring(Entity):
    """ABC for System monitoring."""

    @property
    def name(self):
        """Return the name of the resource."""
        name = SENSOR_TYPES[self.resource][0]
        if self.system is not None:
            return '{} {}'.format(self.system, name)
        return name

    @property
    def system(self):
        """Return the name of the monitored system."""
        return None

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return SENSOR_TYPES[self.resource][1]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.resource][2]

    @property
    def resource(self):
        """Return the name of the resource."""
        raise NotImplementedError()

    @property
    def value(self):
        """Return the current value of the resource."""
        raise NotImplementedError()

    @property
    def state(self):
        """Return the current state."""
        return self.value
