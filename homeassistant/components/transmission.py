"""
Component for monitoring the Transmission BitTorrent client API.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/transmission/
"""
from datetime import timedelta

import logging
import voluptuous as vol

from homeassistant.util import Throttle
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.event import track_time_interval
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_PORT,
    CONF_USERNAME,
    CONF_MONITORED_CONDITIONS,
)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['transmissionrpc==0.11']
_LOGGER = logging.getLogger(__name__)

DOMAIN = 'transmission'
DATA_TRANSMISSION = 'TRANSMISSION'

DEFAULT_NAME = 'Transmission'
DEFAULT_PORT = 9091
TURTLE_MODE = 'turtle_mode'

SENSOR_TYPES = {
    'active_torrents': ['Active Torrents', None],
    'current_status': ['Status', None],
    'download_speed': ['Down Speed', 'MB/s'],
    'paused_torrents': ['Paused Torrents', None],
    'total_torrents': ['Total Torrents', None],
    'upload_speed': ['Up Speed', 'MB/s'],
    'completed_torrents': ['Completed Torrents', None],
    'started_torrents': ['Started Torrents', None],
}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(TURTLE_MODE, default=False): cv.boolean,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=['current_status']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    })
}, extra=vol.ALLOW_EXTRA)

SCAN_INTERVAL = timedelta(minutes=2)


def setup(hass, config):
    hass.data[DATA_TRANSMISSION] = TransmissionData(hass, config)
    hass.data[DATA_TRANSMISSION].init_torrent_list()

    def refresh(event_time):
        hass.data[DATA_TRANSMISSION].update()

    track_time_interval(hass, refresh, SCAN_INTERVAL)

    sensorconfig = {
        'sensors': config[DOMAIN][CONF_MONITORED_CONDITIONS],
        'client_name': config[DOMAIN][CONF_NAME]}
    discovery.load_platform(hass, 'sensor', DOMAIN, sensorconfig)

    if config[DOMAIN][TURTLE_MODE] is True:
        discovery.load_platform(hass, 'switch', DOMAIN, sensorconfig)
    return True


class TransmissionData:
    """Get the latest data and update the states."""
    def __init__(self, hass, config):
        """Initialize the Transmission RPC API"""
        import transmissionrpc
        from transmissionrpc.error import TransmissionError
        try:
            host = config[DOMAIN][CONF_HOST]
            username = config[DOMAIN][CONF_USERNAME]
            password = config[DOMAIN][CONF_PASSWORD]
            port = config[DOMAIN][CONF_PORT]

            api = transmissionrpc.Client(
                host, port=port, user=username, password=password)
            api.session_stats()

            self.data = None
            self.torrents = None
            self.available = True
            self._api = api
            self.completed_torrents = []
            self.started_torrents = []
            self.hass = hass

        except TransmissionError as error:
            if str(error).find("401: Unauthorized"):
                _LOGGER.error("Credentials for"
                              " Transmission client are not valid")
                return

            _LOGGER.warning(
                "Unable to connect to Transmission client: %s:%s", host, port)
            raise PlatformNotReady

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Transmission instance."""
        from transmissionrpc.error import TransmissionError

        try:
            self.data = self._api.session_stats()
            self.torrents = self._api.get_torrents()

            self.check_completed_torrent()
            self.check_started_torrent()

            _LOGGER.debug("Torrent Data updated")
            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client")

    def init_torrent_list(self):
        self.torrents = self._api.get_torrents()
        self.completed_torrents = [
            x.name for x in self.torrents if x.status == "seeding"]
        self.started_torrents = [
            x.name for x in self.torrents if x.status == "downloading"]

    def check_completed_torrent(self):
        """Get completed torrent functionality"""
        actual_torrents = self.torrents
        actual_completed_torrents = [
            var.name for var in actual_torrents if var.status == "seeding"]

        tmp_completed_torrents = list(
            set(actual_completed_torrents).difference(
                self.completed_torrents))

        for var in tmp_completed_torrents:
            self.hass.bus.fire(
                'transmission_downloaded_torrent', {
                    'name': var})

        self.completed_torrents = actual_completed_torrents

    def check_started_torrent(self):
        """Get started torrent functionality"""
        actual_torrents = self.torrents
        actual_started_torrents = [
            var.name for var
            in actual_torrents if var.status == "downloading"]

        tmp_started_torrents = list(
            set(actual_started_torrents).difference(
                self.started_torrents))

        for var in tmp_started_torrents:
            self.hass.bus.fire(
                'transmission_started_torrent', {
                    'name': var})
        self.started_torrents = actual_started_torrents

    def get_started_torrent_count(self):
        return len(self.started_torrents)

    def get_completed_torrent_count(self):
        return len(self.completed_torrents)

    def set_alt_speed_enabled(self, is_enabled):
        self._api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self):
        return self.get_session().alt_speed_enabled

    @Throttle(SCAN_INTERVAL)
    def get_session(self):
        return self._api.get_session()
