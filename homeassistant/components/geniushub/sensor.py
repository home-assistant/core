"""Support for Genius Hub sensor devices."""
from datetime import datetime, timedelta, timezone
import logging

from homeassistant.const import DEVICE_CLASS_BATTERY
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity
from homeassistant.util.dt import utcnow, UTC

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

GH_HAS_BATTERY = [
    'Room Thermostat', 'Genius Valve', 'Room Sensor', 'Radiator Valve']

GH_LEVEL_MAPPING = {
    'error': 'Errors',
    'warning': 'Warnings',
    'information': 'Information'
}


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Genius Hub sensor entities."""
    client = hass.data[DOMAIN]['client']

    sensors = [GeniusDevice(client, d)
               for d in client.hub.device_objs if d.type in GH_HAS_BATTERY]

    issues = [GeniusIssue(client, i)
              for i in list(GH_LEVEL_MAPPING)]

    async_add_entities(sensors + issues, update_before_add=True)


class GeniusDevice(Entity):
    """Representation of a Genius Hub sensor."""

    parallel_updates = True

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
    def icon(self):
        """Return the icon of the sensor."""
        values = self._device._info_raw['childValues']  # noqa; pylint: disable=protected-access

        last_comms = datetime.fromtimestamp(values['lastComms']['val'], tz=UTC)
        interval = timedelta(seconds=values['WakeUp_Interval']['val'] * 3)

        if last_comms < utcnow() - interval:
            return "mdi:battery-unknown"

        level = self.state

        if level > 95:
            return "mdi:battery"
        if level > 85:
            return "mdi:battery-80"
        if level > 70:
            return "mdi:battery-60"
        if level > 55:
            return "mdi:battery-40"
        if level > 45:
            return "mdi:battery-20"

        return "mdi:battery-alert"

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
        level = self._device.state['batteryLevel']
        return level if level != 255 else 0

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attrs = {}
        attrs['assigned_zone'] = self._device.assignedZones[0]['name']

        last_comms = self._device._info_raw['childValues']['lastComms']['val']  # noqa; pylint: disable=protected-access
        attrs['last_comms'] = datetime.fromtimestamp(
            last_comms, tz=UTC).isoformat()

        return {**attrs}


class GeniusIssue(Entity):
    """Representation of a Genius Hub sensor."""

    def __init__(self, client, level):
        """Initialize the sensor."""
        self._hub = client.hub
        self._name = GH_LEVEL_MAPPING[level]
        self._level = level
        self._issues = []

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
    def should_poll(self) -> bool:
        """Return False as the geniushub devices should not be polled."""
        return False

    @property
    def state(self):
        """Return the number of issues."""
        return len(self._issues)

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {'{}_list'.format(self._level): self._issues}

    async def async_update(self):
        """Process the sensor's state data."""
        self._issues = [i['description']
                        for i in self._hub.issues if i['level'] == self._level]
