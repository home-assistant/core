"""Support for local control of entities by emulating a Philips Hue bridge."""
from __future__ import annotations

from functools import cache
import logging

from homeassistant.components import (
    climate,
    cover,
    fan,
    humidifier,
    light,
    media_player,
    scene,
    script,
)
from homeassistant.const import CONF_ENTITIES, CONF_TYPE
from homeassistant.core import HomeAssistant, State, callback, split_entity_id
from homeassistant.helpers import storage
from homeassistant.helpers.event import (
    EventStateChangedData,
    async_track_state_added_domain,
    async_track_state_removed_domain,
)
from homeassistant.helpers.typing import ConfigType, EventType

SUPPORTED_DOMAINS = {
    climate.DOMAIN,
    cover.DOMAIN,
    fan.DOMAIN,
    humidifier.DOMAIN,
    light.DOMAIN,
    media_player.DOMAIN,
    scene.DOMAIN,
    script.DOMAIN,
}


TYPE_ALEXA = "alexa"
TYPE_GOOGLE = "google_home"


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


DEFAULT_LIGHTS_ALL_DIMMABLE = False
DEFAULT_LISTEN_PORT = 8300
DEFAULT_UPNP_BIND_MULTICAST = True
DEFAULT_OFF_MAPS_TO_ON_DOMAINS = {"script", "scene"}
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

ATTR_EMULATED_HUE_NAME = "emulated_hue_name"


_LOGGER = logging.getLogger(__name__)


class Config:
    """Hold configuration variables for the emulated hue bridge."""

    def __init__(self, hass: HomeAssistant, conf: ConfigType, local_ip: str) -> None:
        """Initialize the instance."""
        self.hass = hass
        self.type = conf.get(CONF_TYPE)
        self.numbers: dict[str, str] = {}
        self.store: storage.Store | None = None
        self.cached_states: dict[str, list] = {}
        self._exposed_cache: dict[str, bool] = {}

        if self.type == TYPE_ALEXA:
            _LOGGER.warning(
                "Emulated Hue running in legacy mode because type has been "
                "specified. More info at https://goo.gl/M6tgz8"
            )

        # Get the IP address that will be passed to the Echo during discovery
        self.host_ip_addr: str = conf.get(CONF_HOST_IP) or local_ip

        # Get the port that the Hue bridge will listen on
        self.listen_port: int = conf.get(CONF_LISTEN_PORT) or DEFAULT_LISTEN_PORT

        # Get whether or not UPNP binds to multicast address (239.255.255.250)
        # or to the unicast address (host_ip_addr)
        self.upnp_bind_multicast: bool = conf.get(
            CONF_UPNP_BIND_MULTICAST, DEFAULT_UPNP_BIND_MULTICAST
        )

        # Get domains that cause both "on" and "off" commands to map to "on"
        # This is primarily useful for things like scenes or scripts, which
        # don't really have a concept of being off
        off_maps_to_on_domains = conf.get(CONF_OFF_MAPS_TO_ON_DOMAINS)
        if isinstance(off_maps_to_on_domains, list):
            self.off_maps_to_on_domains = set(off_maps_to_on_domains)
        else:
            self.off_maps_to_on_domains = DEFAULT_OFF_MAPS_TO_ON_DOMAINS

        # Get whether or not entities should be exposed by default, or if only
        # explicitly marked ones will be exposed
        self.expose_by_default: bool = conf.get(
            CONF_EXPOSE_BY_DEFAULT, DEFAULT_EXPOSE_BY_DEFAULT
        )

        # Get domains that are exposed by default when expose_by_default is
        # True
        self.exposed_domains = set(
            conf.get(CONF_EXPOSED_DOMAINS, DEFAULT_EXPOSED_DOMAINS)
        )

        # Calculated effective advertised IP and port for network isolation
        self.advertise_ip: str = conf.get(CONF_ADVERTISE_IP) or self.host_ip_addr

        self.advertise_port: int = conf.get(CONF_ADVERTISE_PORT) or self.listen_port

        self.entities: dict[str, dict[str, str]] = conf.get(CONF_ENTITIES, {})

        self._entities_with_hidden_attr_in_config = {}
        for entity_id in self.entities:
            hidden_value = self.entities[entity_id].get(CONF_ENTITY_HIDDEN)
            if hidden_value is not None:
                self._entities_with_hidden_attr_in_config[entity_id] = hidden_value

        # Get whether all non-dimmable lights should be reported as dimmable
        # for compatibility with older installations.
        self.lights_all_dimmable: bool = conf.get(CONF_LIGHTS_ALL_DIMMABLE) or False

        if self.expose_by_default:
            self.track_domains = set(self.exposed_domains) or SUPPORTED_DOMAINS
        else:
            self.track_domains = {
                split_entity_id(entity_id)[0] for entity_id in self.entities
            }

    async def async_setup(self) -> None:
        """Set up tracking and migrate to storage."""
        hass = self.hass
        self.store = storage.Store(hass, DATA_VERSION, DATA_KEY)  # type: ignore[arg-type]
        numbers_path = hass.config.path(NUMBERS_FILE)
        self.numbers = (
            await storage.async_migrator(hass, numbers_path, self.store) or {}
        )
        async_track_state_added_domain(
            hass, self.track_domains, self._clear_exposed_cache
        )
        async_track_state_removed_domain(
            hass, self.track_domains, self._clear_exposed_cache
        )

    @cache  # pylint: disable=method-cache-max-size-none
    def entity_id_to_number(self, entity_id: str) -> str:
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
        assert self.store is not None
        self.store.async_delay_save(lambda: self.numbers, SAVE_DELAY)
        return number

    def number_to_entity_id(self, number: str) -> str | None:
        """Convert unique number to entity id."""
        if self.type == TYPE_ALEXA:
            return number

        # Google Home
        return self.numbers.get(number)

    def get_entity_name(self, state: State) -> str:
        """Get the name of an entity."""
        if (
            state.entity_id in self.entities
            and CONF_ENTITY_NAME in self.entities[state.entity_id]
        ):
            return self.entities[state.entity_id][CONF_ENTITY_NAME]

        return state.attributes.get(ATTR_EMULATED_HUE_NAME, state.name)

    @cache  # pylint: disable=method-cache-max-size-none
    def get_exposed_states(self) -> list[State]:
        """Return a list of exposed states."""
        state_machine = self.hass.states
        if self.expose_by_default:
            return [
                state
                for state in state_machine.async_all()
                if self.is_state_exposed(state)
            ]
        states: list[State] = []
        for entity_id in self.entities:
            if (state := state_machine.get(entity_id)) and self.is_state_exposed(state):
                states.append(state)
        return states

    @callback
    def _clear_exposed_cache(self, event: EventType[EventStateChangedData]) -> None:
        """Clear the cache of exposed states."""
        self.get_exposed_states.cache_clear()  # pylint: disable=no-member

    def is_state_exposed(self, state: State) -> bool:
        """Cache determine if an entity should be exposed on the emulated bridge."""
        if (exposed := self._exposed_cache.get(state.entity_id)) is not None:
            return exposed
        exposed = self._is_state_exposed(state)
        self._exposed_cache[state.entity_id] = exposed
        return exposed

    def _is_state_exposed(self, state: State) -> bool:
        """Determine if an entity state should be exposed on the emulated bridge.

        Async friendly.
        """
        if state.attributes.get("view") is not None:
            # Ignore entities that are views
            return False

        if state.entity_id in self._entities_with_hidden_attr_in_config:
            return not self._entities_with_hidden_attr_in_config[state.entity_id]

        if not self.expose_by_default:
            return False
        # Expose an entity if the entity's domain is exposed by default and
        # the configuration doesn't explicitly exclude it from being
        # exposed, or if the entity is explicitly exposed
        if state.domain in self.exposed_domains:
            return True

        return False
