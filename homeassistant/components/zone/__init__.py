"""Support for the definition of zones."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import logging
from operator import attrgetter
import sys
from typing import Any, Self, cast

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_PERSONS,
    CONF_ICON,
    CONF_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_RELOAD,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
)
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity_component,
    event,
    service,
    storage,
)
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.loader import bind_hass
from homeassistant.util.location import distance

from .const import ATTR_PASSIVE, ATTR_RADIUS, CONF_PASSIVE, DOMAIN, HOME_ZONE

_LOGGER = logging.getLogger(__name__)

DEFAULT_PASSIVE = False
DEFAULT_RADIUS = 100

ENTITY_ID_FORMAT = "zone.{}"
ENTITY_ID_HOME = ENTITY_ID_FORMAT.format(HOME_ZONE)

ICON_HOME = "mdi:home"
ICON_IMPORT = "mdi:import"

CREATE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_PASSIVE, default=DEFAULT_PASSIVE): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}


UPDATE_FIELDS: VolDictType = {
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_LATITUDE): cv.latitude,
    vol.Optional(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_PASSIVE): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}


def empty_value(value: Any) -> Any:
    """Test if the user has the default config value from adding "zone:"."""
    if isinstance(value, dict) and len(value) == 0:
        return []

    raise vol.Invalid("Not a default value")


CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=[]): vol.Any(
            vol.All(cv.ensure_list, [vol.Schema(CREATE_FIELDS)]),
            empty_value,
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

ENTITY_ID_SORTER = attrgetter("entity_id")

ZONE_ENTITY_IDS = "zone_entity_ids"


@bind_hass
def async_active_zone(
    hass: HomeAssistant, latitude: float, longitude: float, radius: int = 0
) -> State | None:
    """Find the active zone for given latitude, longitude.

    This method must be run in the event loop.
    """
    # Sort entity IDs so that we are deterministic if equal distance to 2 zones
    min_dist: float = sys.maxsize
    closest: State | None = None

    # This can be called before async_setup by device tracker
    zone_entity_ids: Iterable[str] = hass.data.get(ZONE_ENTITY_IDS, ())

    for entity_id in zone_entity_ids:
        if (
            not (zone := hass.states.get(entity_id))
            # Skip unavailable zones
            or zone.state == STATE_UNAVAILABLE
            # Skip passive zones
            or (zone_attrs := zone.attributes).get(ATTR_PASSIVE)
            # Skip zones where we cannot calculate distance
            or (
                zone_dist := distance(
                    latitude,
                    longitude,
                    zone_attrs[ATTR_LATITUDE],
                    zone_attrs[ATTR_LONGITUDE],
                )
            )
            is None
            # Skip zone that are outside the radius aka the
            # lat/long is outside the zone
            or not (zone_dist - (zone_radius := zone_attrs[ATTR_RADIUS]) < radius)
        ):
            continue

        # If have a closest and its not closer than the closest skip it
        if closest and not (
            zone_dist < min_dist
            or (
                # If same distance, prefer smaller zone
                zone_dist == min_dist and zone_radius < closest.attributes[ATTR_RADIUS]
            )
        ):
            continue

        # We got here which means it closer than the previous known closest
        # or equal distance but this one is smaller.
        min_dist = zone_dist
        closest = zone

    return closest


@callback
def async_setup_track_zone_entity_ids(hass: HomeAssistant) -> None:
    """Set up track of entity IDs for zones."""
    zone_entity_ids: list[str] = hass.states.async_entity_ids(DOMAIN)
    hass.data[ZONE_ENTITY_IDS] = zone_entity_ids

    @callback
    def _async_add_zone_entity_id(
        event_: Event[EventStateChangedData],
    ) -> None:
        """Add zone entity ID."""
        zone_entity_ids.append(event_.data["entity_id"])
        zone_entity_ids.sort()

    @callback
    def _async_remove_zone_entity_id(
        event_: Event[EventStateChangedData],
    ) -> None:
        """Remove zone entity ID."""
        zone_entity_ids.remove(event_.data["entity_id"])

    event.async_track_state_added_domain(hass, DOMAIN, _async_add_zone_entity_id)
    event.async_track_state_removed_domain(hass, DOMAIN, _async_remove_zone_entity_id)


def in_zone(zone: State, latitude: float, longitude: float, radius: float = 0) -> bool:
    """Test if given latitude, longitude is in given zone.

    Async friendly.
    """
    if zone.state == STATE_UNAVAILABLE:
        return False

    zone_dist = distance(
        latitude,
        longitude,
        zone.attributes[ATTR_LATITUDE],
        zone.attributes[ATTR_LONGITUDE],
    )

    if zone_dist is None or zone.attributes[ATTR_RADIUS] is None:
        return False
    return zone_dist - radius < cast(float, zone.attributes[ATTR_RADIUS])


class ZoneStorageCollection(collection.DictStorageCollection):
    """Zone collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        return cast(dict, self.CREATE_SCHEMA(data))

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return cast(str, info[CONF_NAME])

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**item, **update_data}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up configured zones as well as Home Assistant zone if necessary."""
    async_setup_track_zone_entity_ids(hass)

    component = entity_component.EntityComponent[Zone](_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.IDLessCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, yaml_collection, Zone
    )

    storage_collection = ZoneStorageCollection(
        storage.Store(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, component, storage_collection, Zone
    )

    if config[DOMAIN]:
        await yaml_collection.async_load(config[DOMAIN])

    await storage_collection.async_load()

    collection.DictStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Remove all zones and load new ones from config."""
        conf = await component.async_prepare_reload(skip_reset=True)
        if conf is None:
            return
        await yaml_collection.async_load(conf[DOMAIN])

    service.async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
        schema=RELOAD_SERVICE_SCHEMA,
    )

    if component.get_entity("zone.home"):
        return True

    home_zone = Zone(_home_conf(hass))
    home_zone.entity_id = ENTITY_ID_HOME
    await component.async_add_entities([home_zone])

    async def core_config_updated(_: Event) -> None:
        """Handle core config updated."""
        await home_zone.async_update_config(_home_conf(hass))

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, core_config_updated)

    hass.data[DOMAIN] = storage_collection

    return True


@callback
def _home_conf(hass: HomeAssistant) -> dict:
    """Return the home zone config."""
    return {
        CONF_NAME: hass.config.location_name,
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
        CONF_RADIUS: hass.config.radius,
        CONF_ICON: ICON_HOME,
        CONF_PASSIVE: False,
    }


async def async_setup_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Set up zone as config entry."""
    storage_collection = cast(ZoneStorageCollection, hass.data[DOMAIN])

    data = dict(config_entry.data)
    data.setdefault(CONF_PASSIVE, DEFAULT_PASSIVE)
    data.setdefault(CONF_RADIUS, DEFAULT_RADIUS)

    await storage_collection.async_create_item(data)

    hass.async_create_task(
        hass.config_entries.async_remove(config_entry.entry_id), eager_start=True
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Will be called once we remove it."""
    return True


class Zone(collection.CollectionEntity):
    """Representation of a Zone."""

    editable: bool
    _attr_should_poll = False

    def __init__(self, config: ConfigType) -> None:
        """Initialize the zone."""
        self._config = config
        self.editable = True
        self._attrs: dict | None = None
        self._remove_listener: Callable[[], None] | None = None
        self._persons_in_zone: set[str] = set()
        self._set_attrs_from_config()

    def _set_attrs_from_config(self) -> None:
        """Set the attributes from the config."""
        config = self._config
        name: str = config[CONF_NAME]
        self._attr_name = name
        self._case_folded_name = name.casefold()
        self._attr_unique_id = config.get(CONF_ID)
        self._attr_icon = config.get(CONF_ICON)

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        zone = cls(config)
        zone.editable = True
        zone._generate_attrs()  # noqa: SLF001
        return zone

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        zone = cls(config)
        zone.editable = False
        zone._generate_attrs()  # noqa: SLF001
        return zone

    @property
    def state(self) -> int:
        """Return the state property really does nothing for a zone."""
        return len(self._persons_in_zone)

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        if self._config == config:
            return
        self._config = config
        self._set_attrs_from_config()
        self._generate_attrs()
        self.async_write_ha_state()

    @callback
    def _person_state_change_listener(self, evt: Event[EventStateChangedData]) -> None:
        person_entity_id = evt.data["entity_id"]
        persons_in_zone = self._persons_in_zone
        cur_count = len(persons_in_zone)
        if self._state_is_in_zone(evt.data["new_state"]):
            persons_in_zone.add(person_entity_id)
        elif person_entity_id in persons_in_zone:
            persons_in_zone.remove(person_entity_id)

        if len(persons_in_zone) != cur_count:
            self._generate_attrs()
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        person_domain = "person"  # avoid circular import
        self._persons_in_zone = {
            state.entity_id
            for state in self.hass.states.async_all(person_domain)
            if self._state_is_in_zone(state)
        }
        self._generate_attrs()

        self.async_on_remove(
            event.async_track_state_change_filtered(
                self.hass,
                event.TrackStates(False, set(), {person_domain}),
                self._person_state_change_listener,
            ).async_remove
        )

    @callback
    def _generate_attrs(self) -> None:
        """Generate new attrs based on config."""
        self._attr_extra_state_attributes = {
            ATTR_LATITUDE: self._config[CONF_LATITUDE],
            ATTR_LONGITUDE: self._config[CONF_LONGITUDE],
            ATTR_RADIUS: self._config[CONF_RADIUS],
            ATTR_PASSIVE: self._config[CONF_PASSIVE],
            ATTR_PERSONS: sorted(self._persons_in_zone),
            ATTR_EDITABLE: self.editable,
        }

    @callback
    def _state_is_in_zone(self, state: State | None) -> bool:
        """Return if given state is in zone."""
        return (
            state is not None
            and state.state
            not in (
                STATE_NOT_HOME,
                STATE_UNKNOWN,
                STATE_UNAVAILABLE,
            )
            and (
                state.state.casefold() == self._case_folded_name
                or (state.state == STATE_HOME and self.entity_id == ENTITY_ID_HOME)
            )
        )
