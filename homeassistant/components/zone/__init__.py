"""Support for the definition of zones."""
import logging
from typing import Any, Dict, Optional, cast

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_HIDDEN,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_ICON,
    CONF_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    EVENT_CORE_CONFIG_UPDATE,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, HomeAssistant, ServiceCall, State, callback
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity,
    entity_component,
    entity_registry,
    service,
    storage,
)
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

CREATE_FIELDS = {
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_LATITUDE): cv.latitude,
    vol.Required(CONF_LONGITUDE): cv.longitude,
    vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS): vol.Coerce(float),
    vol.Optional(CONF_PASSIVE, default=DEFAULT_PASSIVE): cv.boolean,
    vol.Optional(CONF_ICON): cv.icon,
}


UPDATE_FIELDS = {
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
            vol.All(cv.ensure_list, [vol.Schema(CREATE_FIELDS)]), empty_value,
        )
    },
    extra=vol.ALLOW_EXTRA,
)

RELOAD_SERVICE_SCHEMA = vol.Schema({})
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1


@bind_hass
def async_active_zone(
    hass: HomeAssistant, latitude: float, longitude: float, radius: int = 0
) -> Optional[State]:
    """Find the active zone for given latitude, longitude.

    This method must be run in the event loop.
    """
    # Sort entity IDs so that we are deterministic if equal distance to 2 zones
    zones = (
        cast(State, hass.states.get(entity_id))
        for entity_id in sorted(hass.states.async_entity_ids(DOMAIN))
    )

    min_dist = None
    closest = None

    for zone in zones:
        if zone.state == STATE_UNAVAILABLE or zone.attributes.get(ATTR_PASSIVE):
            continue

        zone_dist = distance(
            latitude,
            longitude,
            zone.attributes[ATTR_LATITUDE],
            zone.attributes[ATTR_LONGITUDE],
        )

        if zone_dist is None:
            continue

        within_zone = zone_dist - radius < zone.attributes[ATTR_RADIUS]
        closer_zone = closest is None or zone_dist < min_dist  # type: ignore
        smaller_zone = (
            zone_dist == min_dist
            and zone.attributes[ATTR_RADIUS]
            < cast(State, closest).attributes[ATTR_RADIUS]
        )

        if within_zone and (closer_zone or smaller_zone):
            min_dist = zone_dist
            closest = zone

    return closest


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


class ZoneStorageCollection(collection.StorageCollection):
    """Zone collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    async def _process_create_data(self, data: Dict) -> Dict:
        """Validate the config is valid."""
        return cast(Dict, self.CREATE_SCHEMA(data))

    @callback
    def _get_suggested_id(self, info: Dict) -> str:
        """Suggest an ID based on the config."""
        return cast(str, info[CONF_NAME])

    async def _update_data(self, data: dict, update_data: Dict) -> Dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)
        return {**data, **update_data}


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up configured zones as well as Home Assistant zone if necessary."""
    component = entity_component.EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()

    yaml_collection = collection.IDLessCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    collection.attach_entity_component_collection(
        component, yaml_collection, lambda conf: Zone(conf, False)
    )

    storage_collection = ZoneStorageCollection(
        storage.Store(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}_storage_collection"),
        id_manager,
    )
    collection.attach_entity_component_collection(
        component, storage_collection, lambda conf: Zone(conf, True)
    )

    if config[DOMAIN]:
        await yaml_collection.async_load(config[DOMAIN])

    await storage_collection.async_load()

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    async def _collection_changed(change_type: str, item_id: str, config: Dict) -> None:
        """Handle a collection change: clean up entity registry on removals."""
        if change_type != collection.CHANGE_REMOVED:
            return

        ent_reg = await entity_registry.async_get_registry(hass)
        ent_reg.async_remove(
            cast(str, ent_reg.async_get_entity_id(DOMAIN, DOMAIN, item_id))
        )

    storage_collection.async_add_listener(_collection_changed)

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

    home_zone = Zone(_home_conf(hass), True,)
    home_zone.entity_id = ENTITY_ID_HOME
    await component.async_add_entities([home_zone])

    async def core_config_updated(_: Event) -> None:
        """Handle core config updated."""
        await home_zone.async_update_config(_home_conf(hass))

    hass.bus.async_listen(EVENT_CORE_CONFIG_UPDATE, core_config_updated)

    hass.data[DOMAIN] = storage_collection

    return True


@callback
def _home_conf(hass: HomeAssistant) -> Dict:
    """Return the home zone config."""
    return {
        CONF_NAME: hass.config.location_name,
        CONF_LATITUDE: hass.config.latitude,
        CONF_LONGITUDE: hass.config.longitude,
        CONF_RADIUS: DEFAULT_RADIUS,
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

    hass.async_create_task(hass.config_entries.async_remove(config_entry.entry_id))

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Will be called once we remove it."""
    return True


class Zone(entity.Entity):
    """Representation of a Zone."""

    def __init__(self, config: Dict, editable: bool):
        """Initialize the zone."""
        self._config = config
        self._editable = editable
        self._attrs: Optional[Dict] = None
        self._generate_attrs()

    @property
    def state(self) -> str:
        """Return the state property really does nothing for a zone."""
        return "zoning"

    @property
    def name(self) -> str:
        """Return name."""
        return cast(str, self._config[CONF_NAME])

    @property
    def unique_id(self) -> Optional[str]:
        """Return unique ID."""
        return self._config.get(CONF_ID)

    @property
    def icon(self) -> Optional[str]:
        """Return the icon if any."""
        return self._config.get(CONF_ICON)

    @property
    def state_attributes(self) -> Optional[Dict]:
        """Return the state attributes of the zone."""
        return self._attrs

    async def async_update_config(self, config: Dict) -> None:
        """Handle when the config is updated."""
        self._config = config
        self._generate_attrs()
        self.async_write_ha_state()

    @callback
    def _generate_attrs(self) -> None:
        """Generate new attrs based on config."""
        self._attrs = {
            ATTR_HIDDEN: True,
            ATTR_LATITUDE: self._config[CONF_LATITUDE],
            ATTR_LONGITUDE: self._config[CONF_LONGITUDE],
            ATTR_RADIUS: self._config[CONF_RADIUS],
            ATTR_PASSIVE: self._config[CONF_PASSIVE],
            ATTR_EDITABLE: self._editable,
        }
