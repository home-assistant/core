"""
This component provides basic support for the Philips Hue system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hue/
"""
import json
import logging
import os
import socket

import voluptuous as vol

from homeassistant.components.discovery import SERVICE_HUE
from homeassistant.config import load_yaml_config_file
from homeassistant.const import CONF_FILENAME, CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['phue==1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hue"
SERVICE_HUE_SCENE = "hue_activate_scene"

CONF_BRIDGES = "bridges"

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'
DEFAULT_ALLOW_UNREACHABLE = False

PHUE_CONFIG_FILE = 'phue.conf'

CONF_ALLOW_IN_EMULATED_HUE = "allow_in_emulated_hue"
DEFAULT_ALLOW_IN_EMULATED_HUE = True

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = True

BRIDGE_CONFIG_SCHEMA = vol.Schema([{
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_FILENAME, default=PHUE_CONFIG_FILE): cv.string,
    vol.Optional(CONF_ALLOW_UNREACHABLE,
                 default=DEFAULT_ALLOW_UNREACHABLE): cv.boolean,
    vol.Optional(CONF_ALLOW_IN_EMULATED_HUE,
                 default=DEFAULT_ALLOW_IN_EMULATED_HUE): cv.boolean,
    vol.Optional(CONF_ALLOW_HUE_GROUPS,
                 default=DEFAULT_ALLOW_HUE_GROUPS): cv.boolean,
}])

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BRIDGES, default=[]): BRIDGE_CONFIG_SCHEMA,
    }),
}, extra=vol.ALLOW_EXTRA)

ATTR_GROUP_NAME = "group_name"
ATTR_SCENE_NAME = "scene_name"
SCENE_SCHEMA = vol.Schema({
    vol.Required(ATTR_GROUP_NAME): cv.string,
    vol.Required(ATTR_SCENE_NAME): cv.string,
})

CONFIG_INSTRUCTIONS = """
Press the button on the bridge to register Philips Hue with Home Assistant.

![Location of button on bridge](/static/images/config_philips_hue.jpg)
"""


def setup(hass, config):
    """Set up the Hue platform."""
    config = config.get(DOMAIN)
    if config is None:
        config = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    discovery.listen(
        hass,
        SERVICE_HUE,
        lambda service, discovery_info:
        bridge_discovered(hass, service, discovery_info))

    bridges = config.get(CONF_BRIDGES, [])
    for bridge in bridges:
        filename = bridge.get(CONF_FILENAME)
        allow_unreachable = bridge.get(CONF_ALLOW_UNREACHABLE)
        allow_in_emulated_hue = bridge.get(CONF_ALLOW_IN_EMULATED_HUE)
        allow_hue_groups = bridge.get(CONF_ALLOW_HUE_GROUPS)

        host = bridge.get(CONF_HOST)

        if host is None:
            host = _find_host_from_config(hass, filename)

        if host is None:
            _LOGGER.error("No host found in configuration")
            return False

        setup_bridge(host, hass, filename, allow_unreachable,
                     allow_in_emulated_hue, allow_hue_groups)

    return True


def bridge_discovered(hass, service, discovery_info):
    """Dispatcher for Hue discovery events."""
    if "HASS Bridge" in discovery_info.get('name', ''):
        return

    host = discovery_info.get('host')
    serial = discovery_info.get('serial')

    filename = 'phue-{}.conf'.format(serial)
    setup_bridge(host, hass, filename)


def setup_bridge(host, hass, filename=None, allow_unreachable=False,
                 allow_in_emulated_hue=True, allow_hue_groups=True):
    """Set up a given Hue bridge."""
    # Only register a device once
    if socket.gethostbyname(host) in hass.data[DOMAIN]:
        return

    bridge = HueBridge(host, hass, filename, allow_unreachable,
                       allow_in_emulated_hue, allow_hue_groups)
    bridge.setup()


def _find_host_from_config(hass, filename=PHUE_CONFIG_FILE):
    """Attempt to detect host based on existing configuration."""
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        return None

    try:
        with open(path) as inp:
            return next(iter(json.load(inp).keys()))
    except (ValueError, AttributeError, StopIteration):
        # ValueError if can't parse as JSON
        # AttributeError if JSON value is not a dict
        # StopIteration if no keys
        return None


class HueBridge(object):
    """Manages a single Hue bridge."""

    def __init__(self, host, hass, filename, allow_unreachable=False,
                 allow_in_emulated_hue=True, allow_hue_groups=True):
        """Initialize the system."""
        self.host = host
        self.hass = hass
        self.filename = filename
        self.allow_unreachable = allow_unreachable
        self.allow_in_emulated_hue = allow_in_emulated_hue
        self.allow_hue_groups = allow_hue_groups

        self.bridge = None
        self.lights = {}
        self.lightgroups = {}

        self.configured = False
        self.config_request_id = None

        hass.data[DOMAIN][socket.gethostbyname(host)] = self

    def setup(self):
        """Set up a phue bridge based on host parameter."""
        import phue

        try:
            self.bridge = phue.Bridge(
                self.host,
                config_file_path=self.hass.config.path(self.filename))
        except ConnectionRefusedError:  # Wrong host was given
            _LOGGER.error("Error connecting to the Hue bridge at %s",
                          self.host)
            return
        except phue.PhueRegistrationException:
            _LOGGER.warning("Connected to Hue at %s but not registered.",
                            self.host)
            self.request_configuration()
            return

        # If we came here and configuring this host, mark as done
        if self.config_request_id:
            request_id = self.config_request_id
            self.config_request_id = None
            configurator = self.hass.components.configurator
            configurator.request_done(request_id)

        self.configured = True

        discovery.load_platform(
            self.hass, 'light', DOMAIN,
            {'bridge_id': socket.gethostbyname(self.host)})

        # create a service for calling run_scene directly on the bridge,
        # used to simplify automation rules.
        def hue_activate_scene(call):
            """Service to call directly into bridge to set scenes."""
            group_name = call.data[ATTR_GROUP_NAME]
            scene_name = call.data[ATTR_SCENE_NAME]
            self.bridge.run_scene(group_name, scene_name)

        descriptions = load_yaml_config_file(
            os.path.join(os.path.dirname(__file__), 'services.yaml'))
        self.hass.services.register(
            DOMAIN, SERVICE_HUE_SCENE, hue_activate_scene,
            descriptions.get(SERVICE_HUE_SCENE),
            schema=SCENE_SCHEMA)

    def request_configuration(self):
        """Request configuration steps from the user."""
        configurator = self.hass.components.configurator

        # We got an error if this method is called while we are configuring
        if self.config_request_id:
            configurator.notify_errors(
                self.config_request_id,
                "Failed to register, please try again.")
            return

        self.config_request_id = configurator.request_config(
            "Philips Hue",
            lambda data: self.setup(),
            description=CONFIG_INSTRUCTIONS,
            entity_picture="/static/images/logo_philips_hue.png",
            submit_caption="I have pressed the button"
        )

    def get_api(self):
        """Return the full api dictionary from phue."""
        return self.bridge.get_api()

    def set_light(self, light_id, command):
        """Adjust properties of one or more lights. See phue for details."""
        return self.bridge.set_light(light_id, command)

    def set_group(self, light_id, command):
        """Change light settings for a group. See phue for detail."""
        return self.bridge.set_group(light_id, command)
