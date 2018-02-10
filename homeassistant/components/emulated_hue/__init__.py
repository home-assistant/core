"""
Support for local control of entities by emulating the Phillips Hue bridge.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/emulated_hue/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant import util
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.components.http import REQUIREMENTS  # NOQA
from homeassistant.components.http import HomeAssistantWSGI
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.deprecation import get_deprecated
import homeassistant.helpers.config_validation as cv
from homeassistant.util.json import load_json, save_json
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
CONF_ENTITIES = 'entities'
CONF_ENTITY_NAME = 'name'
CONF_ENTITY_HIDDEN = 'hidden'

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

CONFIG_ENTITY_SCHEMA = vol.Schema({
    vol.Optional(CONF_ENTITY_NAME): cv.string,
    vol.Optional(CONF_ENTITY_HIDDEN): cv.boolean
})

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
            vol.Any(TYPE_ALEXA, TYPE_GOOGLE),
        vol.Optional(CONF_ENTITIES):
            vol.Schema({cv.entity_id: CONFIG_ENTITY_SCHEMA})
    })
}, extra=vol.ALLOW_EXTRA)

ATTR_EMULATED_HUE = 'emulated_hue'
ATTR_EMULATED_HUE_NAME = 'emulated_hue_name'
ATTR_EMULATED_HUE_HIDDEN = 'emulated_hue_hidden'


def setup(hass, yaml_config):
    """Activate the emulated_hue component."""
    config = Config(hass, yaml_config.get(DOMAIN, {}))

    server = HomeAssistantWSGI(
        hass,
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
            _LOGGER.warning(
                'Emulated Hue running in legacy mode because type has been '
                'specified. More info at https://goo.gl/M6tgz8')

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr = conf.get(CONF_HOST_IP)
        if self.host_ip_addr is None:
            self.host_ip_addr = util.get_local_ip()
            _LOGGER.info(
                "Listen IP address not specified, auto-detected address is %s",
                self.host_ip_addr)

        # Get the port that the Hue bridge will listen on
        self.listen_port = conf.get(CONF_LISTEN_PORT)
        if not isinstance(self.listen_port, int):
            self.listen_port = DEFAULT_LISTEN_PORT
            _LOGGER.info(
                "Listen port not specified, defaulting to %s",
                self.listen_port)

        if self.type == TYPE_GOOGLE and self.listen_port != 80:
            _LOGGER.warning("When targeting Google Home, listening port has "
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

        self.entities = conf.get(CONF_ENTITIES, {})

    def entity_id_to_number(self, entity_id):
        """Get a unique number for the entity id."""
        if self.type == TYPE_ALEXA:
            return entity_id

        if self.numbers is None:
            self.numbers = _load_json(self.hass.config.path(NUMBERS_FILE))

        # Google Home
        for number, ent_id in self.numbers.items():
            if entity_id == ent_id:
                return number

        number = '1'
        if self.numbers:
            number = str(max(int(k) for k in self.numbers) + 1)
        self.numbers[number] = entity_id
        save_json(self.hass.config.path(NUMBERS_FILE), self.numbers)
        return number

    def number_to_entity_id(self, number):
        """Convert unique number to entity id."""
        if self.type == TYPE_ALEXA:
            return number

        if self.numbers is None:
            self.numbers = _load_json(self.hass.config.path(NUMBERS_FILE))

        # Google Home
        assert isinstance(number, str)
        return self.numbers.get(number)

    def get_entity_name(self, entity):
        """Get the name of an entity."""
        if entity.entity_id in self.entities and \
                CONF_ENTITY_NAME in self.entities[entity.entity_id]:
            return self.entities[entity.entity_id][CONF_ENTITY_NAME]

        return entity.attributes.get(ATTR_EMULATED_HUE_NAME, entity.name)

    def is_entity_exposed(self, entity):
        """Determine if an entity should be exposed on the emulated bridge.

        Async friendly.
        """
        if entity.attributes.get('view') is not None:
            # Ignore entities that are views
            return False

        domain = entity.domain.lower()
        explicit_expose = entity.attributes.get(ATTR_EMULATED_HUE, None)
        explicit_hidden = entity.attributes.get(ATTR_EMULATED_HUE_HIDDEN, None)

        if entity.entity_id in self.entities and \
                CONF_ENTITY_HIDDEN in self.entities[entity.entity_id]:
            explicit_hidden = \
                self.entities[entity.entity_id][CONF_ENTITY_HIDDEN]

        if explicit_expose is True or explicit_hidden is False:
            expose = True
        elif explicit_expose is False or explicit_hidden is True:
            expose = False
        else:
            expose = None
        get_deprecated(entity.attributes, ATTR_EMULATED_HUE_HIDDEN,
                       ATTR_EMULATED_HUE, None)
        domain_exposed_by_default = \
            self.expose_by_default and domain in self.exposed_domains

        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        is_default_exposed = \
            domain_exposed_by_default and expose is not False

        return is_default_exposed or expose


def _load_json(filename):
    """Wrapper, because we actually want to handle invalid json."""
    try:
        return load_json(filename)
    except HomeAssistantError:
        pass
    return {}
