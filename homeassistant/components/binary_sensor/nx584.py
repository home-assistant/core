"""
homeassistant.components.sensor.nx584
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for exposing nx584 elements as sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.nx584/
"""
import logging
import threading
import time

import requests

from homeassistant.components.binary_sensor import BinarySensorDevice

REQUIREMENTS = ['pynx584==0.2']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup nx584 sensors."""
    from nx584 import client as nx584_client

    host = config.get('host', 'localhost:5007')
    exclude = config.get('exclude_zones', [])

    if not all(isinstance(zone, int) for zone in exclude):
        _LOGGER.error('Invalid excluded zone specified (use zone number)')
        return False

    try:
        client = nx584_client.Client('http://%s' % host)
        zones = client.list_zones()
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to NX584: %s', str(ex))
        return False

    version = [int(v) for v in client.get_version().split('.')]
    if version < [1, 1]:
        _LOGGER.error('NX584 is too old to use for sensors (>=0.2 required)')
        return False

    zone_sensors = {
        zone['number']: NX584ZoneSensor(zone)
        for zone in zones
        if zone['number'] not in exclude}
    if zone_sensors:
        add_devices(zone_sensors.values())
        watcher = NX584Watcher(client, zone_sensors)
        watcher.start()
    else:
        _LOGGER.warning('No zones found on NX584')

    return True


class NX584ZoneSensor(BinarySensorDevice):
    """Represents a NX584 zone as a sensor."""

    def __init__(self, zone):
        self._zone = zone

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._zone['name']

    @property
    def is_on(self):
        # True means "faulted" or "open" or "abnormal state"
        return self._zone['state']


class NX584Watcher(threading.Thread):
    """Event listener thread to process NX584 events."""

    def __init__(self, client, zone_sensors):
        super(NX584Watcher, self).__init__()
        self.daemon = True
        self._client = client
        self._zone_sensors = zone_sensors

    def _process_zone_event(self, event):
        zone = event['zone']
        zone_sensor = self._zone_sensors.get(zone)
        # pylint: disable=protected-access
        if not zone_sensor:
            return
        zone_sensor._zone['state'] = event['zone_state']
        zone_sensor.update_ha_state()

    def _process_events(self, events):
        for event in events:
            if event.get('type') == 'zone_status':
                self._process_zone_event(event)

    def _run(self):
        # Throw away any existing events so we don't replay history
        self._client.get_events()
        while True:
            events = self._client.get_events()
            if events:
                self._process_events(events)

    def run(self):
        while True:
            try:
                self._run()
            except requests.exceptions.ConnectionError:
                _LOGGER.error('Failed to reach NX584 server')
                time.sleep(10)
