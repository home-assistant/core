"""
Support for local control of entities by emulating the Phillips Hue bridge.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_hue/
"""
import asyncio
import json
import logging

import voluptuous as vol

from homeassistant import util
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.components.http import REQUIREMENTS  # NOQA
from homeassistant.components.http import HomeAssistantWSGI
import homeassistant.helpers.config_validation as cv
from .hue_api import (
    HueUsernameView, HueAllLightsStateView, HueOneLightStateView,
    HueOneLightChangeView)
from .upnp import DescriptionXmlView, UPNPResponderThread

DOMAIN = 'emulated_hue'

_LOGGER = logging.getLogger(__name__)

NUMBERS_FILE = 'emulated_hue_ids.json'

CONF_HOST_IP = 'host_ip'
CONF_LISTEN_PORT = 'listen_port'
CONF_ADVERTISE_IP = 'advertise_ip'
CONF_ADVERTISE_PORT = 'advertise_port'
CONF_UPNP_BIND_MULTICAST = 'upnp_bind_multicast'
CONF_OFF_MAPS_TO_ON_DOMAINS = 'off_maps_to_on_domains'
CONF_EXPOSE_BY_DEFAULT = 'expose_by_default'
CONF_EXPOSED_DOMAINS = 'exposed_domains'
CONF_TYPE = 'type'

TYPE_ALEXA = 'alexa'
TYPE_GOOGLE = 'google_home'

DEFAULT_LISTEN_PORT = 8300
DEFAULT_UPNP_BIND_MULTICAST = True
DEFAULT_OFF_MAPS_TO_ON_DOMAINS = ['script', 'scene']
DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    'switch', 'light', 'group', 'input_boolean', 'media_player', 'fan'
]
DEFAULT_TYPE = TYPE_GOOGLE

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST_IP): cv.string,
        vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
        vol.Optional(CONF_ADVERTISE_IP): cv.string,
        vol.Optional(CONF_ADVERTISE_PORT): cv.port,
        vol.Optional(CONF_UPNP_BIND_MULTICAST): cv.boolean,
        vol.Optional(CONF_OFF_MAPS_TO_ON_DOMAINS): cv.ensure_list,
        vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
        vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
        vol.Optional(CONF_TYPE, default=DEFAULT_TYPE):
            vol.Any(TYPE_ALEXA, TYPE_GOOGLE)
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_EMULATED_HUE = 'emulated_hue'


def setup(hass, yaml_config):
    """Activate the emulated_hue component."""
    config = Config(hass, yaml_config.get(DOMAIN, {}))

    server = HomeAssistantWSGI(
        hass,
        development=False,
        server_host=config.host_ip_addr,
        server_port=config.listen_port,
        api_password=None,
        ssl_certificate=None,
        ssl_key=None,
        cors_origins=None,
        use_x_forwarded_for=False,
        trusted_networks=[],
        login_threshold=0,
        is_ban_enabled=False
    )

    server.register_view(DescriptionXmlView(config))
    server.register_view(HueUsernameView)
    server.register_view(HueAllLightsStateView(config))
    server.register_view(HueOneLightStateView(config))
    server.register_view(HueOneLightChangeView(config))

    upnp_listener = UPNPResponderThread(
        config.host_ip_addr, config.listen_port,
        config.upnp_bind_multicast, config.advertise_ip,
        config.advertise_port)

    @asyncio.coroutine
    def stop_emulated_hue_bridge(event):
        """Stop the emulated hue bridge."""
        upnp_listener.stop()
        yield from server.stop()

    @asyncio.coroutine
    def start_emulated_hue_bridge(event):
        """Start the emulated hue bridge."""
        upnp_listener.start()
        yield from server.start()
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, stop_emulated_hue_bridge)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_emulated_hue_bridge)

    return True


class Config(object):
    """Hold configuration variables for the emulated hue bridge."""

    def __init__(self, hass, conf):
        """Initialize the instance."""
        self.hass = hass
        self.type = conf.get(CONF_TYPE)
        self.numbers = None
        self.cached_states = {}

        if self.type == TYPE_ALEXA:
            _LOGGER.warning("Alexa type is deprecated and will be removed in a"
                            "future version")

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr = conf.get(CONF_HOST_IP)
        if self.host_ip_addr is None:
            self.host_ip_addr = util.get_local_ip()
            _LOGGER.warning(
                "Listen IP address not specified, auto-detected address is %s",
                self.host_ip_addr)

        # Get the port that the Hue bridge will listen on
        self.listen_port = conf.get(CONF_LISTEN_PORT)
        if not isinstance(self.listen_port, int):
            self.listen_port = DEFAULT_LISTEN_PORT
            _LOGGER.warning(
                "Listen port not specified, defaulting to %s",
                self.listen_port)

        if self.type == TYPE_GOOGLE and self.listen_port != 80:
            _LOGGER.warning("When targetting Google Home, listening port has "
                            "to be port 80")

        # Get whether or not UPNP binds to multicast address (239.255.255.250)
        # or to the unicast address (host_ip_addr)
        self.upnp_bind_multicast = conf.get(
            CONF_UPNP_BIND_MULTICAST, DEFAULT_UPNP_BIND_MULTICAST)

        # Get domains that cause both "on" and "off" commands to map to "on"
        # This is primarily useful for things like scenes or scripts, which
        # don't really have a concept of being off
        self.off_maps_to_on_domains = conf.get(CONF_OFF_MAPS_TO_ON_DOMAINS)
        if not isinstance(self.off_maps_to_on_domains, list):
            self.off_maps_to_on_domains = DEFAULT_OFF_MAPS_TO_ON_DOMAINS

        # Get whether or not entities should be exposed by default, or if only
        # explicitly marked ones will be exposed
        self.expose_by_default = conf.get(
            CONF_EXPOSE_BY_DEFAULT, DEFAULT_EXPOSE_BY_DEFAULT)

        # Get domains that are exposed by default when expose_by_default is
        # True
        self.exposed_domains = conf.get(
            CONF_EXPOSED_DOMAINS, DEFAULT_EXPOSED_DOMAINS)

        # Calculated effective advertised IP and port for network isolation
        self.advertise_ip = conf.get(
            CONF_ADVERTISE_IP) or self.host_ip_addr

        self.advertise_port = conf.get(
            CONF_ADVERTISE_PORT) or self.listen_port

    def entity_id_to_number(self, entity_id):
        """Get a unique number for the entity id."""
        if self.type == TYPE_ALEXA:
            return entity_id

        if self.numbers is None:
            self.numbers = self._load_numbers_json()

        # Google Home
        for number, ent_id in self.numbers.items():
            if entity_id == ent_id:
                return number

        number = str(len(self.numbers) + 1)
        self.numbers[number] = entity_id
        self._save_numbers_json()
        return number

    def number_to_entity_id(self, number):
        """Convert unique number to entity id."""
        if self.type == TYPE_ALEXA:
            return number

        if self.numbers is None:
            self.numbers = self._load_numbers_json()

        # Google Home
        assert isinstance(number, str)
        return self.numbers.get(number)

    def is_entity_exposed(self, entity):
        """Determine if an entity should be exposed on the emulated bridge.

        Async friendly.
        """
        if entity.attributes.get('view') is not None:
            # Ignore entities that are views
            return False

        domain = entity.domain.lower()
        explicit_expose = entity.attributes.get(ATTR_EMULATED_HUE, None)

        domain_exposed_by_default = \
            self.expose_by_default and domain in self.exposed_domains

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = \
            domain_exposed_by_default and explicit_expose is not False

        return is_default_exposed or explicit_expose

    def _load_numbers_json(self):
        """Set up helper method to load numbers json."""
        try:
            with open(self.hass.config.path(NUMBERS_FILE),
                      encoding='utf-8') as fil:
                return json.loads(fil.read())
        except (OSError, ValueError) as err:
            # OSError if file not found or unaccessible/no permissions
            # ValueError if could not parse JSON
            if not isinstance(err, FileNotFoundError):
                _LOGGER.warning("Failed to open %s: %s", NUMBERS_FILE, err)
            return {}

    def _save_numbers_json(self):
        """Set up helper method to save numbers json."""
        try:
            with open(self.hass.config.path(NUMBERS_FILE), 'w',
                      encoding='utf-8') as fil:
                fil.write(json.dumps(self.numbers))
        except OSError as err:
            # OSError if file write permissions
            _LOGGER.warning("Failed to write %s: %s", NUMBERS_FILE, err)
