"""
This component provides basic support for the Philips Hue system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/hue/
"""
import asyncio
import json
import ipaddress
import logging
import os

import async_timeout
import voluptuous as vol

from homeassistant.core import callback
from homeassistant.components.discovery import SERVICE_HUE
from homeassistant.const import CONF_FILENAME, CONF_HOST
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import discovery, aiohttp_client
from homeassistant import config_entries
from homeassistant.util.json import save_json

REQUIREMENTS = ['aiohue==1.2.0']

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hue"
SERVICE_HUE_SCENE = "hue_activate_scene"
API_NUPNP = 'https://www.meethue.com/api/nupnp'

CONF_BRIDGES = "bridges"

CONF_ALLOW_UNREACHABLE = 'allow_unreachable'
DEFAULT_ALLOW_UNREACHABLE = False

PHUE_CONFIG_FILE = 'phue.conf'

CONF_ALLOW_HUE_GROUPS = "allow_hue_groups"
DEFAULT_ALLOW_HUE_GROUPS = True

BRIDGE_CONFIG_SCHEMA = vol.Schema({
    # Validate as IP address and then convert back to a string.
    vol.Required(CONF_HOST): vol.All(ipaddress.ip_address, cv.string),
    vol.Optional(CONF_FILENAME, default=PHUE_CONFIG_FILE): cv.string,
    vol.Optional(CONF_ALLOW_UNREACHABLE,
                 default=DEFAULT_ALLOW_UNREACHABLE): cv.boolean,
    vol.Optional(CONF_ALLOW_HUE_GROUPS,
                 default=DEFAULT_ALLOW_HUE_GROUPS): cv.boolean,
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_BRIDGES):
            vol.All(cv.ensure_list, [BRIDGE_CONFIG_SCHEMA]),
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


async def async_setup(hass, config):
    """Set up the Hue platform."""
    conf = config.get(DOMAIN)
    if conf is None:
        conf = {}

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    async def async_bridge_discovered(service, discovery_info):
        """Dispatcher for Hue discovery events."""
        # Ignore emulated hue
        if "HASS Bridge" in discovery_info.get('name', ''):
            return

        await async_setup_bridge(
            hass, discovery_info['host'],
            'phue-{}.conf'.format(discovery_info['serial']))

    discovery.async_listen(hass, SERVICE_HUE, async_bridge_discovered)

    # User has configured bridges
    if CONF_BRIDGES in conf:
        bridges = conf[CONF_BRIDGES]

    # Component is part of config but no bridges specified, discover.
    elif DOMAIN in config:
        # discover from nupnp
        websession = aiohttp_client.async_get_clientsession(hass)

        async with websession.get(API_NUPNP) as req:
            hosts = await req.json()

        # Run through config schema to populate defaults
        bridges = [BRIDGE_CONFIG_SCHEMA({
            CONF_HOST: entry['internalipaddress'],
            CONF_FILENAME: '.hue_{}.conf'.format(entry['id']),
        }) for entry in hosts]

    else:
        # Component not specified in config, we're loaded via discovery
        bridges = []

    if not bridges:
        return True

    await asyncio.wait([
        async_setup_bridge(
            hass, bridge[CONF_HOST], bridge[CONF_FILENAME],
            bridge[CONF_ALLOW_UNREACHABLE], bridge[CONF_ALLOW_HUE_GROUPS]
        ) for bridge in bridges
    ])

    return True


async def async_setup_bridge(
        hass, host, filename=None,
        allow_unreachable=DEFAULT_ALLOW_UNREACHABLE,
        allow_hue_groups=DEFAULT_ALLOW_HUE_GROUPS,
        username=None):
    """Set up a given Hue bridge."""
    assert filename or username, 'Need to pass at least a username or filename'

    # Only register a device once
    if host in hass.data[DOMAIN]:
        return

    if username is None:
        username = await hass.async_add_job(
            _find_username_from_config, hass, filename)

    bridge = HueBridge(host, hass, filename, username, allow_unreachable,
                       allow_hue_groups)
    await bridge.async_setup()
    hass.data[DOMAIN][host] = bridge


def _find_username_from_config(hass, filename):
    """Load username from config."""
    path = hass.config.path(filename)

    if not os.path.isfile(path):
        return None

    with open(path) as inp:
        return list(json.load(inp).values())[0]['username']


class HueBridge(object):
    """Manages a single Hue bridge."""

    def __init__(self, host, hass, filename, username,
                 allow_unreachable=False, allow_groups=True):
        """Initialize the system."""
        self.host = host
        self.hass = hass
        self.filename = filename
        self.username = username
        self.allow_unreachable = allow_unreachable
        self.allow_groups = allow_groups
        self.available = True
        self.config_request_id = None
        self.api = None

    async def async_setup(self):
        """Set up a phue bridge based on host parameter."""
        import aiohue

        api = aiohue.Bridge(
            self.host,
            username=self.username,
            websession=aiohttp_client.async_get_clientsession(self.hass)
        )

        try:
            with async_timeout.timeout(5):
                # Initialize bridge and validate our username
                if not self.username:
                    await api.create_user('home-assistant')
                await api.initialize()
        except (aiohue.LinkButtonNotPressed, aiohue.Unauthorized):
            _LOGGER.warning("Connected to Hue at %s but not registered.",
                            self.host)
            self.async_request_configuration()
            return
        except (asyncio.TimeoutError, aiohue.RequestError):
            _LOGGER.error("Error connecting to the Hue bridge at %s",
                          self.host)
            return
        except aiohue.AiohueException:
            _LOGGER.exception('Unknown Hue linking error occurred')
            self.async_request_configuration()
            return
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unknown error connecting with Hue bridge at %s",
                              self.host)
            return

        # If we came here and configuring this host, mark as done
        if self.config_request_id:
            request_id = self.config_request_id
            self.config_request_id = None
            self.hass.components.configurator.async_request_done(request_id)

            self.username = api.username

            # Save config file
            await self.hass.async_add_job(
                save_json, self.hass.config.path(self.filename),
                {self.host: {'username': api.username}})

        self.api = api

        self.hass.async_add_job(discovery.async_load_platform(
            self.hass, 'light', DOMAIN,
            {'host': self.host}))

        self.hass.services.async_register(
            DOMAIN, SERVICE_HUE_SCENE, self.hue_activate_scene,
            schema=SCENE_SCHEMA)

    @callback
    def async_request_configuration(self):
        """Request configuration steps from the user."""
        configurator = self.hass.components.configurator

        # We got an error if this method is called while we are configuring
        if self.config_request_id:
            configurator.async_notify_errors(
                self.config_request_id,
                "Failed to register, please try again.")
            return

        async def config_callback(data):
            """Callback for configurator data."""
            await self.async_setup()

        self.config_request_id = configurator.async_request_config(
            "Philips Hue", config_callback,
            description=CONFIG_INSTRUCTIONS,
            entity_picture="/static/images/logo_philips_hue.png",
            submit_caption="I have pressed the button"
        )

    async def hue_activate_scene(self, call, updated=False):
        """Service to call directly into bridge to set scenes."""
        group_name = call.data[ATTR_GROUP_NAME]
        scene_name = call.data[ATTR_SCENE_NAME]

        group = next(
            (group for group in self.api.groups.values()
             if group.name == group_name), None)

        scene_id = next(
            (scene.id for scene in self.api.scenes.values()
             if scene.name == scene_name), None)

        # If we can't find it, fetch latest info.
        if not updated and (group is None or scene_id is None):
            await self.api.groups.update()
            await self.api.scenes.update()
            await self.hue_activate_scene(call, updated=True)
            return

        if group is None:
            _LOGGER.warning('Unable to find group %s', group_name)
            return

        if scene_id is None:
            _LOGGER.warning('Unable to find scene %s', scene_name)
            return

        await group.set_action(scene=scene_id)


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
                reason='discover_timeout'
            )

        if not bridges:
            return self.async_abort(
                reason='no_bridges'
            )

        # Find already configured hosts
        configured_hosts = set(
            entry.data['host'] for entry
            in self.hass.config_entries.async_entries(DOMAIN))

        hosts = [bridge.host for bridge in bridges
                 if bridge.host not in configured_hosts]

        if not hosts:
            return self.async_abort(
                reason='all_configured'
            )

        elif len(hosts) == 1:
            self.host = hosts[0]
            return await self.async_step_link()

        return self.async_show_form(
            step_id='init',
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
                errors['base'] = 'register_failed'
            except aiohue.AiohueException:
                errors['base'] = 'linking'
                _LOGGER.exception('Unknown Hue linking error occurred')
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
            errors=errors,
        )


async def async_setup_entry(hass, entry):
    """Set up a bridge for a config entry."""
    await async_setup_bridge(hass, entry.data['host'],
                             username=entry.data['username'])
    return True
