"""Support for Genius Hub sensor devices."""
from datetime import datetime
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

GH_HAS_BATTERY = [
    'Room Thermostat', 'Genius Valve', 'Room Sensor', 'Radiator Valve']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    client = hass.data[DOMAIN]['client']

    sensors = [GeniusDevice(client, d)
               for d in client.hub.device_objs if d.type in GH_HAS_BATTERY]

    async_add_entities(sensors)


class GeniusDevice(Entity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, client, device):
        """Initialize the sensor."""
        self._client = client
        self._device = device

        self._name = '{} {}'.format(device.type, device.id)

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._refresh)

    @callback
    def _refresh(self):
        self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return DEVICE_CLASS_BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return '%'

    @property
    def should_poll(self) -> bool:
        """Return False as the geniushub devices should not be polled."""
        return False

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._device.state['batteryLevel']

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}
        attrs['assigned_zone'] = self._device.assignedZones[0]['name']

        last_comms = self._device._info_raw['childValues']['lastComms']['val']  # noqa; pylint: disable=protected-access
        attrs['last_comms'] = datetime.utcfromtimestamp(
            last_comms).isoformat()

        return {**attrs}
