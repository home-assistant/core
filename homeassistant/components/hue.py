"""
homeassistant.components.hue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Philips Hue bridge.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hue/
"""

import logging
import socket
from datetime import timedelta
from urllib.parse import urlparse

from homeassistant import bootstrap
from homeassistant.util import Throttle
from homeassistant.loader import get_component
from homeassistant.components import discovery
from homeassistant.const import (
    CONF_HOST, ATTR_SERVICE, ATTR_DISCOVERED, EVENT_PLATFORM_DISCOVERED)

DOMAIN = 'hue'
REQUIREMENTS = ['phue==0.8']

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_UPDATES = timedelta(milliseconds=100)

PHUE_CONFIG_FILE = "phue.conf"
DISCOVER_LIGHTS = 'hue.lights'

ATTR_HUE_LIGHTS = 'lights'
ATTR_HUE_BRIDGEID = 'bridgeid'
ATTR_HUE_BRIDGEIP = 'ipaddress'

HUEBRIDGE = None

# Map ip to request id for configuring
_CONFIGURING = {}


def setup(hass, config):
    """
    Setup a Hue bridge

    Set up a 'global' to contain bridge instances to be called.
    If the bridge is non-local, it cannot be discovered. Multiple bridge can be
    listed in configuration.
    Setup discovery
    """

    # This dict will hold all bridges. The dict key is the bridgeid.
    # It's much easier to just use 'host', but deals better with multiple IPs
    # or DHCP swtiching bridge ip?
    global HUEBRIDGE
    HUEBRIDGE = {}

    # Fetch config
    conf = config.get(DOMAIN, {})
    if not isinstance(conf, list):
        conf = [conf]
    for entry in conf:
        host = entry.get(CONF_HOST, None)
        if not host:
            continue
        # FIXME / This can only happen when discovery beats configuration
        # loading right?
        if host in _CONFIGURING:
            continue

        _LOGGER.info('Attempting bridge setup for %s', host)
        setup_huebridge(hass, host)

    comp_name = 'light'
    component = get_component(comp_name)
    bootstrap.setup_component(hass, component.DOMAIN, config)

    def huebridge_discovered(service, info):
        """
        Called when a Hue bridge is discovered.
        Response from netdisco recovery is an URI, we just need the host/ip
        ro initialize the python bridge module
        """
        hostname = urlparse(info[1]).hostname
        setup_huebridge(hass, hostname)
    discovery.listen(hass, discovery.SERVICE_HUE, huebridge_discovered)

    return True


def setup_huebridge(hass, host):
    """ Setup a phue bridge based on host parameter. """
    import phue

    # Create bridge object which will try and connect to the referenced host/ip
    # If we're not allowed (registration exception), start a config request
    try:
        bridge = phue.Bridge(
            host,
            config_file_path=hass.config.path(PHUE_CONFIG_FILE))
        bridge_id = bridge.get_api().get('config').get(ATTR_HUE_BRIDGEID)
    except (
            ConnectionRefusedError,
            OSError):
        _LOGGER.error("Error connecting to the Hue bridge at %s", host)
        return
    except phue.PhueRegistrationException:
        _LOGGER.warning("Connected to Hue at %s but not registered.", host)
        request_configuration(hass, host)
        return

    # If we came here and configuring this host, mark as done
    if host in _CONFIGURING:
        request_id = _CONFIGURING.pop(host)
        configurator = get_component('configurator')
        configurator.request_done(request_id)

    # Add instanciated bridge to our own control global
    if HUEBRIDGE.get(bridge_id):
        _LOGGER.info('Bridge %s already initialized, skipping', bridge_id)
        return
    HUEBRIDGE[bridge_id] = HueBridge(hass, bridge)


def request_configuration(hass, host):
    """ Request configuration steps from the user. """
    configurator = get_component('configurator')

    # We got an error if this method is called while we are configuring
    if host in _CONFIGURING:
        configurator.notify_errors(
            _CONFIGURING[host], "Failed to register, please try again.")
        return

    # pylint: disable=unused-argument
    def hue_configuration_callback(data):
        """ Actions to do when our configuration callback is called. """
        setup_huebridge(hass, host)

    _CONFIGURING[host] = configurator.request_config(
        hass, "Philips Hue", hue_configuration_callback,
        description=("Press the button on the bridge to register Philips Hue "
                     "with Home Assistant."),
        description_image="/static/images/config_philips_hue.jpg",
        submit_caption="I have pressed the button"
    )


class HueBridge(object):
    """
    This manages a Hue bridge
    Gets the latest data and update the states
    """

    def __init__(self, hass, bridge):
        # This will be used to control devices from their platform modules
        self.hass = hass
        self._bridge = bridge
        # self.set_light = self._bridge.set_light
        self.states = {}

        bconfig = self.get_apidata().get('config')
        self.bridge_id = bconfig.get(ATTR_HUE_BRIDGEID)
        self.bridge_ip = bconfig.get(ATTR_HUE_BRIDGEIP)

        # Support limitations in DiY zigbee bridge 'deconz'
        if bconfig.get('name') == 'RaspBee-GW':
            self.bridge_type = 'deconz'
        else:
            self.bridge_type = 'hue'

        # FIXME / debuglog
        _LOGGER.warning('New bridge: %s/%s', self.bridge_ip, self.bridge_id)
        self.update()

    def set_light(self, light_id, command):
        self._bridge.set_light(int(light_id), command)

    def get_state(self, dev_type, dev_id):
        try:
            return self.states[dev_type][dev_id]
        except ValueError:
            return None

    def get_apidata(self):
        """ Refresh state data from bridge """
        try:
            return  self._bridge.get_api()
        except socket.error:
            # socket.error when we cannot reach Hue
            _LOGGER.error("Cannot reach the bridge")
            return

    #@Throttle(MIN_TIME_BETWEEN_UPDATES, MIN_TIME_BETWEEN_FORCED_UPDATES)
    def update(self):
        """
        Fetch latest info from the bridge.

        """
        _LOGGER.warning('Refreshing data from bridge: %s', self.bridge_id)
        lastids = {key: list(val.keys()) for key,val in self.states.items()}

        self.states[ATTR_HUE_LIGHTS] = self.get_apidata().get(ATTR_HUE_LIGHTS)
        if not isinstance(self.states, dict):
            _LOGGER.error("Got unexpected result from Hue API")
            return

        # Calculate differences between last and current
        newids = {
            key: list(set(self.states[key]) - set(lastids.get(key,[])))
            for key in self.states
        }

        if newids[ATTR_HUE_LIGHTS]:
            # FIXME / debuglog
            _LOGGER.warning('Sending discovery event: %s', newids[ATTR_HUE_LIGHTS])
            self.hass.bus.fire(EVENT_PLATFORM_DISCOVERED, {
                ATTR_SERVICE: DISCOVER_LIGHTS,
                ATTR_DISCOVERED: {
                    ATTR_HUE_BRIDGEID: self.bridge_id,
                    ATTR_HUE_LIGHTS: newids[ATTR_HUE_LIGHTS],
                }
            })
