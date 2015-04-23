"""
homeassistant.components.sensor.transmission
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Monitors Transmission BitTorrent client API

Configuration:

To use the Transmission sensor you will need to add something like the
following to your config/configuration.yaml

sensor:
    platform: transmission
    name: Transmission
    host: 192.168.1.26
    port: 9091
    username: YOUR_USERNAME
    password: YOUR_PASSWORD
    monitored_variables:
        - type: 'current_status'
        - type: 'download_speed'
        - type: 'upload_speed'

VARIABLES:

host
*Required
This is the IP address of your Transmission Daemon
Example: 192.168.1.32

port
*Optional
The port your Transmission daemon uses, defaults to 9091
Example: 8080

username
*Required
Your Transmission username

password
*Required
Your Transmission password

name
*Optional
The name to use when displaying this Transmission instance

monitored_variables
*Required
An array specifying the variables to monitor.

These are the variables for the monitored_variables array:

type
*Required
The variable you wish to monitor, see the configuration example above for a
list of all available variables


"""

from homeassistant.util import Throttle
from datetime import timedelta
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

from homeassistant.helpers.entity import Entity
# pylint: disable=no-name-in-module, import-error
import transmissionrpc

from transmissionrpc.error import TransmissionError

import logging

SENSOR_TYPES = {
    'current_status': ['Status', ''],
    'download_speed': ['Down Speed', 'MB/s'],
    'upload_speed': ['Up Speed', 'MB/s']
}

_LOGGER = logging.getLogger(__name__)

_THROTTLED_REFRESH = None


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors """
    host = config.get(CONF_HOST)
    username = config.get(CONF_USERNAME, None)
    password = config.get(CONF_PASSWORD, None)
    port = config.get('port', 9091)

    name = config.get("name", "Transmission")
    if not host:
        _LOGGER.error('Missing config variable %s', CONF_HOST)
        return False

    # import logging
    # logging.getLogger('transmissionrpc').setLevel(logging.DEBUG)

    transmission_api = transmissionrpc.Client(
        host, port=port, user=username, password=password)
    try:
        transmission_api.session_stats()
    except TransmissionError:
        _LOGGER.exception("Connection to Transmission API failed.")
        return False

    # pylint: disable=global-statement
    global _THROTTLED_REFRESH
    _THROTTLED_REFRESH = Throttle(timedelta(seconds=1))(
        transmission_api.session_stats)

    dev = []
    for variable in config['monitored_variables']:
        if variable['type'] not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable['type'])
        else:
            dev.append(TransmissionSensor(
                variable['type'], transmission_api, name))

    add_devices(dev)


class TransmissionSensor(Entity):
    """ A Transmission sensor """

    def __init__(self, sensor_type, transmission_client, client_name):
        self._name = SENSOR_TYPES[sensor_type][0]
        self.transmission_client = transmission_client
        self.type = sensor_type
        self.client_name = client_name
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        return self.client_name + ' ' + self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    def refresh_transmission_data(self):
        """ Calls the throttled Transmission refresh method. """
        if _THROTTLED_REFRESH is not None:
            try:
                _THROTTLED_REFRESH()
            except TransmissionError:
                _LOGGER.exception(
                    self.name + "  Connection to Transmission API failed."
                )

    def update(self):
        """ Gets the latest from Transmission and updates the state. """
        self.refresh_transmission_data()
        if self.type == 'current_status':
            if self.transmission_client.session:
                upload = self.transmission_client.session.uploadSpeed
                download = self.transmission_client.session.downloadSpeed
                if upload > 0 and download > 0:
                    self._state = 'Up/Down'
                elif upload > 0 and download == 0:
                    self._state = 'Seeding'
                elif upload == 0 and download > 0:
                    self._state = 'Downloading'
                else:
                    self._state = 'Idle'
            else:
                self._state = 'Unknown'

        if self.transmission_client.session:
            if self.type == 'download_speed':
                mb_spd = float(self.transmission_client.session.downloadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
            elif self.type == 'upload_speed':
                mb_spd = float(self.transmission_client.session.uploadSpeed)
                mb_spd = mb_spd / 1024 / 1024
                self._state = round(mb_spd, 2 if mb_spd < 0.1 else 1)
