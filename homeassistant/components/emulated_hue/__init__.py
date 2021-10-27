"""Support for local control of entities by emulating a Philips Hue bridge."""
import logging

from aiohttp import web
import voluptuous as vol

from homeassistant.components.network import async_get_source_ip
from homeassistant.components.network.const import PUBLIC_TARGET_IP
from homeassistant.const import (
    CONF_ENTITIES,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import storage
import homeassistant.helpers.config_validation as cv

from .hue_api import (
    HueAllGroupsStateView,
    HueAllLightsStateView,
    HueConfigView,
    HueFullStateView,
    HueGroupView,
    HueOneLightChangeView,
    HueOneLightStateView,
    HueUnauthorizedUser,
    HueUsernameView,
)
from .upnp import DescriptionXmlView, create_upnp_datagram_endpoint

DOMAIN = "emulated_hue"

_LOGGER = logging.getLogger(__name__)

NUMBERS_FILE = "emulated_hue_ids.json"
DATA_KEY = "emulated_hue.ids"
DATA_VERSION = "1"
SAVE_DELAY = 60

CONF_ADVERTISE_IP = "advertise_ip"
CONF_ADVERTISE_PORT = "advertise_port"
CONF_ENTITY_HIDDEN = "hidden"
CONF_ENTITY_NAME = "name"
CONF_EXPOSE_BY_DEFAULT = "expose_by_default"
CONF_EXPOSED_DOMAINS = "exposed_domains"
CONF_HOST_IP = "host_ip"
CONF_LIGHTS_ALL_DIMMABLE = "lights_all_dimmable"
CONF_LISTEN_PORT = "listen_port"
CONF_OFF_MAPS_TO_ON_DOMAINS = "off_maps_to_on_domains"
CONF_UPNP_BIND_MULTICAST = "upnp_bind_multicast"

TYPE_ALEXA = "alexa"
TYPE_GOOGLE = "google_home"

DEFAULT_LIGHTS_ALL_DIMMABLE = False
DEFAULT_LISTEN_PORT = 8300
DEFAULT_UPNP_BIND_MULTICAST = True
DEFAULT_OFF_MAPS_TO_ON_DOMAINS = ["script", "scene"]
DEFAULT_EXPOSE_BY_DEFAULT = True
DEFAULT_EXPOSED_DOMAINS = [
    "switch",
    "light",
    "group",
    "input_boolean",
    "media_player",
    "fan",
]
DEFAULT_TYPE = TYPE_GOOGLE

CONFIG_ENTITY_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENTITY_NAME): cv.string,
        vol.Optional(CONF_ENTITY_HIDDEN): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_HOST_IP): cv.string,
                vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): cv.port,
                vol.Optional(CONF_ADVERTISE_IP): cv.string,
                vol.Optional(CONF_ADVERTISE_PORT): cv.port,
                vol.Optional(CONF_UPNP_BIND_MULTICAST): cv.boolean,
                vol.Optional(CONF_OFF_MAPS_TO_ON_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_EXPOSE_BY_DEFAULT): cv.boolean,
                vol.Optional(CONF_EXPOSED_DOMAINS): cv.ensure_list,
                vol.Optional(CONF_TYPE, default=DEFAULT_TYPE): vol.Any(
                    TYPE_ALEXA, TYPE_GOOGLE
                ),
                vol.Optional(CONF_ENTITIES): vol.Schema(
                    {cv.entity_id: CONFIG_ENTITY_SCHEMA}
                ),
                vol.Optional(
                    CONF_LIGHTS_ALL_DIMMABLE, default=DEFAULT_LIGHTS_ALL_DIMMABLE
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

ATTR_EMULATED_HUE_NAME = "emulated_hue_name"


async def async_setup(hass, yaml_config):
    """Activate the emulated_hue component."""
    local_ip = await async_get_source_ip(hass, PUBLIC_TARGET_IP)
    config = Config(hass, yaml_config.get(DOMAIN, {}), local_ip)
    await config.async_setup()

    app = web.Application()
    app["hass"] = hass

    # We misunderstood the startup signal. You're not allowed to change
    # anything during startup. Temp workaround.
    # pylint: disable=protected-access
    app._on_startup.freeze()
    await app.startup()

    runner = None
    site = None

    DescriptionXmlView(config).register(app, app.router)
    HueUsernameView().register(app, app.router)
    HueConfigView(config).register(app, app.router)
    HueUnauthorizedUser().register(app, app.router)
    HueAllLightsStateView(config).register(app, app.router)
    HueOneLightStateView(config).register(app, app.router)
    HueOneLightChangeView(config).register(app, app.router)
    HueAllGroupsStateView(config).register(app, app.router)
    HueGroupView(config).register(app, app.router)
    HueFullStateView(config).register(app, app.router)

    listen = create_upnp_datagram_endpoint(
        config.host_ip_addr,
        config.upnp_bind_multicast,
        config.advertise_ip,
        config.advertise_port or config.listen_port,
    )
    protocol = None

    async def stop_emulated_hue_bridge(event):
        """Stop the emulated hue bridge."""
        nonlocal protocol
        nonlocal site
        nonlocal runner

        if protocol:
            protocol.close()
        if site:
            await site.stop()
        if runner:
            await runner.cleanup()

    async def start_emulated_hue_bridge(event):
        """Start the emulated hue bridge."""
        nonlocal protocol
        nonlocal site
        nonlocal runner

        _, protocol = await listen

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, config.host_ip_addr, config.listen_port)

        try:
            await site.start()
        except OSError as error:
            _LOGGER.error(
                "Failed to create HTTP server at port %d: %s", config.listen_port, error
            )
            if protocol:
                protocol.close()
        else:
            hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_STOP, stop_emulated_hue_bridge
            )

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_emulated_hue_bridge)

    return True


class Config:
    """Hold configuration variables for the emulated hue bridge."""

    def __init__(self, hass, conf, local_ip):
        """Initialize the instance."""
        self.hass = hass
        self.type = conf.get(CONF_TYPE)
        self.numbers = None
        self.store = None
        self.cached_states = {}
        self._exposed_cache = {}

        if self.type == TYPE_ALEXA:
            _LOGGER.warning(
                "Emulated Hue running in legacy mode because type has been "
                "specified. More info at https://goo.gl/M6tgz8"
            )

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr = conf.get(CONF_HOST_IP)
        if self.host_ip_addr is None:
            self.host_ip_addr = local_ip

        # Get the port that the Hue bridge will listen on
        self.listen_port = conf.get(CONF_LISTEN_PORT)
        if not isinstance(self.listen_port, int):
            self.listen_port = DEFAULT_LISTEN_PORT
            _LOGGER.info(
                "Listen port not specified, defaulting to %s", self.listen_port
            )

        # Get whether or not UPNP binds to multicast address (239.255.255.250)
        # or to the unicast address (host_ip_addr)
        self.upnp_bind_multicast = conf.get(
            CONF_UPNP_BIND_MULTICAST, DEFAULT_UPNP_BIND_MULTICAST
        )

        # Get domains that cause both "on" and "off" commands to map to "on"
        # This is primarily useful for things like scenes or scripts, which
        # don't really have a concept of being off
        self.off_maps_to_on_domains = conf.get(CONF_OFF_MAPS_TO_ON_DOMAINS)
        if not isinstance(self.off_maps_to_on_domains, list):
            self.off_maps_to_on_domains = DEFAULT_OFF_MAPS_TO_ON_DOMAINS

        # Get whether or not entities should be exposed by default, or if only
        # explicitly marked ones will be exposed
        self.expose_by_default = conf.get(
            CONF_EXPOSE_BY_DEFAULT, DEFAULT_EXPOSE_BY_DEFAULT
        )

        # Get domains that are exposed by default when expose_by_default is
        # True
        self.exposed_domains = set(
            conf.get(CONF_EXPOSED_DOMAINS, DEFAULT_EXPOSED_DOMAINS)
        )

        # Calculated effective advertised IP and port for network isolation
        self.advertise_ip = conf.get(CONF_ADVERTISE_IP) or self.host_ip_addr

        self.advertise_port = conf.get(CONF_ADVERTISE_PORT) or self.listen_port

        self.entities = conf.get(CONF_ENTITIES, {})

        self._entities_with_hidden_attr_in_config = {}
        for entity_id in self.entities:
            hidden_value = self.entities[entity_id].get(CONF_ENTITY_HIDDEN)
            if hidden_value is not None:
                self._entities_with_hidden_attr_in_config[entity_id] = hidden_value

        # Get whether all non-dimmable lights should be reported as dimmable
        # for compatibility with older installations.
        self.lights_all_dimmable = conf.get(CONF_LIGHTS_ALL_DIMMABLE)

    async def async_setup(self):
        """Set up and migrate to storage."""
        self.store = storage.Store(self.hass, DATA_VERSION, DATA_KEY)
        self.numbers = (
            await storage.async_migrator(
                self.hass, self.hass.config.path(NUMBERS_FILE), self.store
            )
            or {}
        )

    def entity_id_to_number(self, entity_id):
        """Get a unique number for the entity id."""
        if self.type == TYPE_ALEXA:
            return entity_id

        # Google Home
        for number, ent_id in self.numbers.items():
            if entity_id == ent_id:
                return number

        number = "1"
        if self.numbers:
            number = str(max(int(k) for k in self.numbers) + 1)
        self.numbers[number] = entity_id
        self.store.async_delay_save(lambda: self.numbers, SAVE_DELAY)
        return number

    def number_to_entity_id(self, number):
        """Convert unique number to entity id."""
        if self.type == TYPE_ALEXA:
            return number

        # Google Home
        assert isinstance(number, str)
        return self.numbers.get(number)

    def get_entity_name(self, entity):
        """Get the name of an entity."""
        if (
            entity.entity_id in self.entities
            and CONF_ENTITY_NAME in self.entities[entity.entity_id]
        ):
            return self.entities[entity.entity_id][CONF_ENTITY_NAME]

        return entity.attributes.get(ATTR_EMULATED_HUE_NAME, entity.name)

    def is_entity_exposed(self, entity):
        """Cache determine if an entity should be exposed on the emulated bridge."""
        entity_id = entity.entity_id
        if entity_id not in self._exposed_cache:
            self._exposed_cache[entity_id] = self._is_entity_exposed(entity)
        return self._exposed_cache[entity_id]

    def filter_exposed_entities(self, states):
        """Filter a list of all states down to exposed entities."""
        exposed = []
        for entity in states:
            entity_id = entity.entity_id
            if entity_id not in self._exposed_cache:
                self._exposed_cache[entity_id] = self._is_entity_exposed(entity)
            if self._exposed_cache[entity_id]:
                exposed.append(entity)
        return exposed

    def _is_entity_exposed(self, entity):
        """Determine if an entity should be exposed on the emulated bridge.

        Async friendly.
        """
        if entity.attributes.get("view") is not None:
            # Ignore entities that are views
            return False

        if entity.entity_id in self._entities_with_hidden_attr_in_config:
            return not self._entities_with_hidden_attr_in_config[entity.entity_id]

        if not self.expose_by_default:
            return False
        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        if entity.domain in self.exposed_domains:
            return True

        return False
