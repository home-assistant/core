"""Support for Roku."""
import logging

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_ROKU
from homeassistant.const import CONF_HOST
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'roku'

SERVICE_SCAN = 'roku_scan'

ATTR_ROKU = 'roku'

DATA_ROKU = 'data_roku'

NOTIFICATION_ID = 'roku_notification'
NOTIFICATION_TITLE = 'Roku Setup'
NOTIFICATION_SCAN_ID = 'roku_scan_notification'
NOTIFICATION_SCAN_TITLE = 'Roku Scan'


CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [vol.Schema({
        vol.Required(CONF_HOST): cv.string
    })])
}, extra=vol.ALLOW_EXTRA)

# Currently no attributes but it might change later
ROKU_SCAN_SCHEMA = vol.Schema({})


def setup(hass, config):
    """Set up the Roku component."""
    hass.data[DATA_ROKU] = {}

    def service_handler(service):
        """Handle service calls."""
        if service.service == SERVICE_SCAN:
            scan_for_rokus(hass)

    def roku_discovered(service, info):
        """Set up an Roku that was auto discovered."""
        _setup_roku(hass, config, {
            CONF_HOST: info['host']
        })

    discovery.listen(hass, SERVICE_ROKU, roku_discovered)

    for conf in config.get(DOMAIN, []):
        _setup_roku(hass, config, conf)

    hass.services.register(
        DOMAIN, SERVICE_SCAN, service_handler,
        schema=ROKU_SCAN_SCHEMA)

    return True


def scan_for_rokus(hass):
    """Scan for devices and present a notification of the ones found."""
    from roku import Roku, RokuException
    rokus = Roku.discover()

    devices = []
    for roku in rokus:
        try:
            r_info = roku.device_info
        except RokuException:  # skip non-roku device
            continue
        devices.append('Name: {0}<br />Host: {1}<br />'.format(
            r_info.userdevicename if r_info.userdevicename
            else "{} {}".format(r_info.modelname, r_info.sernum),
            roku.host))
    if not devices:
        devices = ['No device(s) found']

    hass.components.persistent_notification.create(
        'The following devices were found:<br /><br />' +
        '<br /><br />'.join(devices),
        title=NOTIFICATION_SCAN_TITLE,
        notification_id=NOTIFICATION_SCAN_ID)


def _setup_roku(hass, hass_config, roku_config):
    """Set up a Roku."""
    from roku import Roku
    host = roku_config[CONF_HOST]

    if host in hass.data[DATA_ROKU]:
        return

    roku = Roku(host)
    r_info = roku.device_info

    hass.data[DATA_ROKU][host] = {
        ATTR_ROKU: r_info.sernum
    }

    discovery.load_platform(
        hass, 'media_player', DOMAIN, roku_config, hass_config)

    discovery.load_platform(
        hass, 'remote', DOMAIN, roku_config, hass_config)
