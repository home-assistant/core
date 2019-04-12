"""Support for the Transmission BitTorrent client API."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_PASSWORD, CONF_PORT,
    CONF_SCAN_INTERVAL, CONF_USERNAME)
from homeassistant.helpers import config_validation as cv, discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.helpers.event import track_time_interval

REQUIREMENTS = ['transmissionrpc==0.11']

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'transmission'
DATA_UPDATED = 'transmission_data_updated'
DATA_TRANSMISSION = 'data_transmission'

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

DEFAULT_SCAN_INTERVAL = timedelta(seconds=120)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(TURTLE_MODE, default=False): cv.boolean,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL):
            cv.time_period,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=['current_status']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    })
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up the Transmission Component."""
    host = config[DOMAIN][CONF_HOST]
    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    port = config[DOMAIN][CONF_PORT]
    scan_interval = config[DOMAIN][CONF_SCAN_INTERVAL]

    import transmissionrpc
    from transmissionrpc.error import TransmissionError
    try:
        api = transmissionrpc.Client(
            host, port=port, user=username, password=password)
        api.session_stats()
    except TransmissionError as error:
        if str(error).find("401: Unauthorized"):
            _LOGGER.error("Credentials for"
                          " Transmission client are not valid")
        return False

    tm_data = hass.data[DATA_TRANSMISSION] = TransmissionData(
        hass, config, api)

    tm_data.update()
    tm_data.init_torrent_list()

    def refresh(event_time):
        """Get the latest data from Transmission."""
        tm_data.update()

    track_time_interval(hass, refresh, scan_interval)

    sensorconfig = {
        'sensors': config[DOMAIN][CONF_MONITORED_CONDITIONS],
        'client_name': config[DOMAIN][CONF_NAME]}

    discovery.load_platform(hass, 'sensor', DOMAIN, sensorconfig, config)

    if config[DOMAIN][TURTLE_MODE]:
        discovery.load_platform(hass, 'switch', DOMAIN, sensorconfig, config)

    return True


class TransmissionData:
    """Get the latest data and update the states."""

    def __init__(self, hass, config, api):
        """Initialize the Transmission RPC API."""
        self.data = None
        self.torrents = None
        self.session = None
        self.available = True
        self._api = api
        self.completed_torrents = []
        self.started_torrents = []
        self.hass = hass

    def update(self):
        """Get the latest data from Transmission instance."""
        from transmissionrpc.error import TransmissionError

        try:
            self.data = self._api.session_stats()
            self.torrents = self._api.get_torrents()
            self.session = self._api.get_session()

            self.check_completed_torrent()
            self.check_started_torrent()

            dispatcher_send(self.hass, DATA_UPDATED)

            _LOGGER.debug("Torrent Data updated")
            self.available = True
        except TransmissionError:
            self.available = False
            _LOGGER.error("Unable to connect to Transmission client")

    def init_torrent_list(self):
        """Initialize torrent lists."""
        self.torrents = self._api.get_torrents()
        self.completed_torrents = [
            x.name for x in self.torrents if x.status == "seeding"]
        self.started_torrents = [
            x.name for x in self.torrents if x.status == "downloading"]

    def check_completed_torrent(self):
        """Get completed torrent functionality."""
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
        """Get started torrent functionality."""
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
        """Get the number of started torrents."""
        return len(self.started_torrents)

    def get_completed_torrent_count(self):
        """Get the number of completed torrents."""
        return len(self.completed_torrents)

    def set_alt_speed_enabled(self, is_enabled):
        """Set the alternative speed flag."""
        self._api.set_session(alt_speed_enabled=is_enabled)

    def get_alt_speed_enabled(self):
        """Get the alternative speed flag."""
        if self.session is None:
            return None

        return self.session.alt_speed_enabled
