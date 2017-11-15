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

from homeassistant.config import load_yaml_config_file
from homeassistant.const import CONF_FILENAME, CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery

REQUIREMENTS = ['phue==1.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hue"
SERVICE_HUE_SCENE = "hue_activate_scene"

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'
DEFAULT_ALLOW_UNREACHABLE = False

PHUE_CONFIG_FILE = 'phue.conf'

CONF_ALLOW_IN_EMULATED_HUE = "allow_in_emulated_hue"
DEFAULT_ALLOW_IN_EMULATED_HUE = True

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = True

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_ALLOW_UNREACHABLE): cv.boolean,
        vol.Optional(CONF_FILENAME): cv.string,
        vol.Optional(CONF_ALLOW_IN_EMULATED_HUE): cv.boolean,
        vol.Optional(CONF_ALLOW_HUE_GROUPS,
                     default=DEFAULT_ALLOW_HUE_GROUPS): cv.boolean,
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


def _find_host_from_config(hass, filename=PHUE_CONFIG_FILE):
    """Attempt to detect host based on existing configuration."""
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        return None

    try:
        with open(path) as inp:
            return next(json.loads(''.join(inp)).keys().__iter__())
    except (ValueError, AttributeError, StopIteration):
        # ValueError if can't parse as JSON
        # AttributeError if JSON value is not a dict
        # StopIteration if no keys
        return None


def setup(hass, config):
    """Set up the Hue platform."""
    # Default needed in case of discovery
    config = config.get(DOMAIN)
    if config is None:
        config = {}
    filename = config.get(CONF_FILENAME, PHUE_CONFIG_FILE)
    allow_unreachable = config.get(CONF_ALLOW_UNREACHABLE,
                                   DEFAULT_ALLOW_UNREACHABLE)
    allow_in_emulated_hue = config.get(CONF_ALLOW_IN_EMULATED_HUE,
                                       DEFAULT_ALLOW_IN_EMULATED_HUE)
    allow_hue_groups = config.get(CONF_ALLOW_HUE_GROUPS,
                                  DEFAULT_ALLOW_HUE_GROUPS)

    host = config.get(CONF_HOST, None)

    if host is None:
        host = _find_host_from_config(hass, filename)

    if host is None:
        _LOGGER.error("No host found in configuration")
        return False

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    bridge = HueBridge(host, hass, filename, allow_unreachable,
                       allow_in_emulated_hue, allow_hue_groups)
    hass.data[DOMAIN][socket.gethostbyname(host)] = bridge
    bridge.setup()


    return True


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

        self.configured = False
        self.config_request_id = None

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
