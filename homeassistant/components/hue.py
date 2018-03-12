"""
This component provides basic support for the Philips Hue system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hue/
"""
import asyncio
import json
from functools import partial
import logging
import os
import socket

import async_timeout
import requests
import voluptuous as vol

from homeassistant.components.discovery import SERVICE_HUE
from homeassistant.const import CONF_FILENAME, CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery, aiohttp_client
from homeassistant import config_entries

REQUIREMENTS = ['phue==1.0', 'aiohue==0.3.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hue"
SERVICE_HUE_SCENE = "hue_activate_scene"
API_NUPNP = 'https://www.meethue.com/api/nupnp'

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
        vol.Optional(CONF_BRIDGES): BRIDGE_CONFIG_SCHEMA,
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
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    discovery.listen(
        hass,
        SERVICE_HUE,
        lambda service, discovery_info:
        bridge_discovered(hass, service, discovery_info))

    # User has configured bridges
    if CONF_BRIDGES in conf:
        bridges = conf[CONF_BRIDGES]
    # Component is part of config but no bridges specified, discover.
    elif DOMAIN in config:
        # discover from nupnp
        hosts = requests.get(API_NUPNP).json()
        bridges = [{
            CONF_HOST: entry['internalipaddress'],
            CONF_FILENAME: '.hue_{}.conf'.format(entry['id']),
        } for entry in hosts]
    else:
        # Component not specified in config, we're loaded via discovery
        bridges = []

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
                 allow_in_emulated_hue=True, allow_hue_groups=True,
                 username=None):
    """Set up a given Hue bridge."""
    # Only register a device once
    if socket.gethostbyname(host) in hass.data[DOMAIN]:
        return

    bridge = HueBridge(host, hass, filename, username, allow_unreachable,
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

    def __init__(self, host, hass, filename, username, allow_unreachable=False,
                 allow_in_emulated_hue=True, allow_hue_groups=True):
        """Initialize the system."""
        self.host = host
        self.bridge_id = socket.gethostbyname(host)
        self.hass = hass
        self.filename = filename
        self.username = username
        self.allow_unreachable = allow_unreachable
        self.allow_in_emulated_hue = allow_in_emulated_hue
        self.allow_hue_groups = allow_hue_groups

        self.available = True
        self.bridge = None
        self.lights = {}
        self.lightgroups = {}

        self.configured = False
        self.config_request_id = None

        hass.data[DOMAIN][self.bridge_id] = self

    def setup(self):
        """Set up a phue bridge based on host parameter."""
        import phue

        try:
            kwargs = {}
            if self.username is not None:
                kwargs['username'] = self.username
            if self.filename is not None:
                kwargs['config_file_path'] = \
                    self.hass.config.path(self.filename)
            self.bridge = phue.Bridge(self.host, **kwargs)
        except OSError:  # Wrong host was given
            _LOGGER.error("Error connecting to the Hue bridge at %s",
                          self.host)
            return
        except phue.PhueRegistrationException:
            _LOGGER.warning("Connected to Hue at %s but not registered.",
                            self.host)
            self.request_configuration()
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting with Hue bridge at %s",
                              self.host)
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
            {'bridge_id': self.bridge_id})

        # create a service for calling run_scene directly on the bridge,
        # used to simplify automation rules.
        def hue_activate_scene(call):
            """Service to call directly into bridge to set scenes."""
            group_name = call.data[ATTR_GROUP_NAME]
            scene_name = call.data[ATTR_SCENE_NAME]
            self.bridge.run_scene(group_name, scene_name)

        self.hass.services.register(
            DOMAIN, SERVICE_HUE_SCENE, hue_activate_scene,
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


@config_entries.HANDLERS.register(DOMAIN)
class HueFlowHandler(config_entries.ConfigFlowHandler):
    """Handle a Hue config flow."""

    VERSION = 1

    def __init__(self):
        """Initialize the Hue flow."""
        self.host = None

    @property
    def _websession(self):
        """Return a websession.

        Cannot assign in init because hass variable is not set yet.
        """
        return aiohttp_client.async_get_clientsession(self.hass)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        from aiohue.discovery import discover_nupnp

        if user_input is not None:
            self.host = user_input['host']
            return await self.async_step_link()

        try:
            with async_timeout.timeout(5):
                bridges = await discover_nupnp(websession=self._websession)
        except asyncio.TimeoutError:
            return self.async_abort(
                reason='Unable to discover Hue bridges.'
            )

        if not bridges:
            return self.async_abort(
                reason='No Philips Hue bridges discovered.'
            )

        # Find already configured hosts
        configured_hosts = set(
            entry.data['host'] for entry
            in self.hass.config_entries.async_entries(DOMAIN))

        hosts = [bridge.host for bridge in bridges
                 if bridge.host not in configured_hosts]

        if not hosts:
            return self.async_abort(
                reason='All Philips Hue bridges are already configured.'
            )

        elif len(hosts) == 1:
            self.host = hosts[0]
            return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
            title='Pick Hue Bridge',
            data_schema=vol.Schema({
                vol.Required('host'): vol.In(hosts)
            })
        )

    async def async_step_link(self, user_input=None):
        """Attempt to link with the Hue bridge."""
        import aiohue
        errors = {}

        if user_input is not None:
            bridge = aiohue.Bridge(self.host, websession=self._websession)
            try:
                with async_timeout.timeout(5):
                    # Create auth token
                    await bridge.create_user('home-assistant')
                    # Fetches name and id
                    await bridge.initialize()
            except (asyncio.TimeoutError, aiohue.RequestError,
                    aiohue.LinkButtonNotPressed):
                errors['base'] = 'Failed to register, please try again.'
            except aiohue.AiohueException:
                errors['base'] = 'Unknown linking error occurred.'
                _LOGGER.exception('Uknown Hue linking error occurred')
            else:
                return self.async_create_entry(
                    title=bridge.config.name,
                    data={
                        'host': bridge.host,
                        'bridge_id': bridge.config.bridgeid,
                        'username': bridge.username,
                    }
                )

        return self.async_show_form(
            step_id='link',
            title='Link Hub',
            description=CONFIG_INSTRUCTIONS,
            errors=errors,
        )


async def async_setup_entry(hass, entry):
    """Set up a bridge for a config entry."""
    await hass.async_add_job(partial(
        setup_bridge, entry.data['host'], hass,
        username=entry.data['username']))
    return True
