"""Support for tracking people."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Self

import voluptuous as vol

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.components import persistent_notification, websocket_api
from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SourceType,
)
from homeassistant.components.zone import ENTITY_ID_HOME
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_GPS_ACCURACY,
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_ID,
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
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
    split_entity_id,
)
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity_registry as er,
    service,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType
from homeassistant.loader import bind_hass

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE = "source"
ATTR_USER_ID = "user_id"
ATTR_DEVICE_TRACKERS = "device_trackers"

CONF_DEVICE_TRACKERS = "device_trackers"
CONF_USER_ID = "user_id"
CONF_PICTURE = "picture"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 2
# Device tracker states to ignore
IGNORE_STATES = (STATE_UNKNOWN, STATE_UNAVAILABLE)

PERSON_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_USER_ID): cv.string,
        vol.Optional(CONF_DEVICE_TRACKERS, default=[]): vol.All(
            cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)
        ),
        vol.Optional(CONF_PICTURE): cv.string,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(DOMAIN, default=[]): vol.All(
            cv.ensure_list, cv.remove_falsy, [PERSON_SCHEMA]
        )
    },
    extra=vol.ALLOW_EXTRA,
)


@bind_hass
async def async_create_person(
    hass: HomeAssistant,
    name: str,
    *,
    user_id: str | None = None,
    device_trackers: list[str] | None = None,
) -> None:
    """Create a new person."""
    await hass.data[DOMAIN][1].async_create_item(
        {
            ATTR_NAME: name,
            ATTR_USER_ID: user_id,
            CONF_DEVICE_TRACKERS: device_trackers or [],
        }
    )


@bind_hass
async def async_add_user_device_tracker(
    hass: HomeAssistant, user_id: str, device_tracker_entity_id: str
) -> None:
    """Add a device tracker to a person linked to a user."""
    coll: PersonStorageCollection = hass.data[DOMAIN][1]

    for person in coll.async_items():
        if person.get(ATTR_USER_ID) != user_id:
            continue

        device_trackers = person[CONF_DEVICE_TRACKERS]

        if device_tracker_entity_id in device_trackers:
            return

        await coll.async_update_item(
            person[CONF_ID],
            {CONF_DEVICE_TRACKERS: [*device_trackers, device_tracker_entity_id]},
        )
        break


@callback
def persons_with_entity(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all persons that reference the entity."""
    if (
        DOMAIN not in hass.data
        or split_entity_id(entity_id)[0] != DEVICE_TRACKER_DOMAIN
    ):
        return []

    component: EntityComponent[Person] = hass.data[DOMAIN][2]

    return [
        person_entity.entity_id
        for person_entity in component.entities
        if entity_id in person_entity.device_trackers
    ]


@callback
def entities_in_person(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Return all entities belonging to a person."""
    if DOMAIN not in hass.data:
        return []

    component: EntityComponent[Person] = hass.data[DOMAIN][2]

    if (person_entity := component.get_entity(entity_id)) is None:
        return []

    return person_entity.device_trackers


CREATE_FIELDS: VolDictType = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_USER_ID): vol.Any(str, None),
    vol.Optional(CONF_DEVICE_TRACKERS, default=list): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    vol.Optional(CONF_PICTURE): vol.Any(str, None),
}


UPDATE_FIELDS: VolDictType = {
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_USER_ID): vol.Any(str, None),
    vol.Optional(CONF_DEVICE_TRACKERS, default=list): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    vol.Optional(CONF_PICTURE): vol.Any(str, None),
}


class PersonStore(Store):
    """Person storage."""

    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version.

        Migrate storage to use format of collection helper.
        """
        return {"items": old_data["persons"]}


class PersonStorageCollection(collection.DictStorageCollection):
    """Person collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    def __init__(
        self,
        store: Store,
        id_manager: collection.IDManager,
        yaml_collection: collection.YamlCollection,
    ) -> None:
        """Initialize a person storage collection."""
        super().__init__(store, id_manager)
        self.yaml_collection = yaml_collection

    async def _async_load_data(self) -> collection.SerializedStorageCollection | None:
        """Load the data.

        A past bug caused onboarding to create invalid person objects.
        This patches it up.
        """
        data = await super()._async_load_data()

        if data is None:
            return data

        for person in data["items"]:
            if person[CONF_DEVICE_TRACKERS] is None:
                person[CONF_DEVICE_TRACKERS] = []

        return data

    async def async_load(self) -> None:
        """Load the Storage collection."""
        await super().async_load()
        self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED,
            self._entity_registry_updated,
            event_filter=self._entity_registry_filter,
        )

    @callback
    def _entity_registry_filter(
        self, event_data: er.EventEntityRegistryUpdatedData
    ) -> bool:
        """Filter entity registry events."""
        return (
            event_data["action"] == "remove"
            and split_entity_id(event_data["entity_id"])[0] == "device_tracker"
        )

    async def _entity_registry_updated(
        self, event: Event[er.EventEntityRegistryUpdatedData]
    ) -> None:
        """Handle entity registry updated."""
        entity_id = event.data["entity_id"]
        for person in list(self.data.values()):
            if entity_id not in person[CONF_DEVICE_TRACKERS]:
                continue

            await self.async_update_item(
                person[CONF_ID],
                {
                    CONF_DEVICE_TRACKERS: [
                        devt
                        for devt in person[CONF_DEVICE_TRACKERS]
                        if devt != entity_id
                    ]
                },
            )

    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)

        if (user_id := data.get(CONF_USER_ID)) is not None:
            await self._validate_user_id(user_id)

        return data

    @callback
    def _get_suggested_id(self, info: dict[str, str]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, item: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)

        user_id: str | None = update_data.get(CONF_USER_ID)

        if user_id is not None and user_id != item.get(CONF_USER_ID):
            await self._validate_user_id(user_id)

        return {**item, **update_data}

    async def _validate_user_id(self, user_id: str) -> None:
        """Validate the used user_id."""
        if await self.hass.auth.async_get_user(user_id) is None:
            raise ValueError("User does not exist")

        for persons in (self.data.values(), self.yaml_collection.async_items()):
            if any(person for person in persons if person.get(CONF_USER_ID) == user_id):
                raise ValueError("User already taken")


class PersonStorageCollectionWebsocket(collection.DictStorageCollectionWebsocket):
    """Class to expose storage collection management over websocket."""

    def ws_list_item(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """List persons."""
        yaml, storage, _ = hass.data[DOMAIN]
        connection.send_result(
            msg[ATTR_ID],
            {"storage": storage.async_items(), "config": yaml.async_items()},
        )


async def filter_yaml_data(hass: HomeAssistant, persons: list[dict]) -> list[dict]:
    """Validate YAML data that we can't validate via schema."""
    filtered = []
    person_invalid_user = []

    for person_conf in persons:
        user_id = person_conf.get(CONF_USER_ID)

        if user_id is not None and await hass.auth.async_get_user(user_id) is None:
            _LOGGER.error(
                "Invalid user_id detected for person %s",
                person_conf[CONF_ID],
            )
            person_invalid_user.append(
                f"- Person {person_conf[CONF_NAME]} (id: {person_conf[CONF_ID]}) points"
                f" at invalid user {user_id}"
            )
            continue

        filtered.append(person_conf)

    if person_invalid_user:
        persistent_notification.async_create(
            hass,
            f"""
The following persons point at invalid users:

{"- ".join(person_invalid_user)}
            """,
            "Invalid Person Configuration",
            DOMAIN,
        )

    return filtered


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the person component."""
    entity_component = EntityComponent[Person](_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()
    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    storage_collection = PersonStorageCollection(
        PersonStore(hass, STORAGE_VERSION, STORAGE_KEY),
        id_manager,
        yaml_collection,
    )

    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, entity_component, yaml_collection, Person
    )
    collection.sync_entity_lifecycle(
        hass, DOMAIN, DOMAIN, entity_component, storage_collection, Person
    )

    await yaml_collection.async_load(
        await filter_yaml_data(hass, config.get(DOMAIN, []))
    )
    await storage_collection.async_load()

    hass.data[DOMAIN] = (yaml_collection, storage_collection, entity_component)

    PersonStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)

    async def _handle_user_removed(event: Event) -> None:
        """Handle a user being removed."""
        user_id = event.data[ATTR_USER_ID]
        for person in storage_collection.async_items():
            if person[CONF_USER_ID] == user_id:
                await storage_collection.async_update_item(
                    person[CONF_ID], {CONF_USER_ID: None}
                )

    hass.bus.async_listen(EVENT_USER_REMOVED, _handle_user_removed)

    async def async_reload_yaml(call: ServiceCall) -> None:
        """Reload YAML."""
        conf = await entity_component.async_prepare_reload(skip_reset=True)
        if conf is None:
            return
        await yaml_collection.async_load(
            await filter_yaml_data(hass, conf.get(DOMAIN, []))
        )

    service.async_register_admin_service(
        hass, DOMAIN, SERVICE_RELOAD, async_reload_yaml
    )

    return True


class Person(
    collection.CollectionEntity,
    RestoreEntity,
):
    """Represent a tracked person."""

    _entity_component_unrecorded_attributes = frozenset({ATTR_DEVICE_TRACKERS})

    _attr_should_poll = False
    editable: bool

    def __init__(self, config: dict[str, Any]) -> None:
        """Set up person."""
        self._config = config
        self._latitude: float | None = None
        self._longitude: float | None = None
        self._gps_accuracy: float | None = None
        self._source: str | None = None
        self._unsub_track_device: Callable[[], None] | None = None
        self._attr_state: str | None = None
        self.device_trackers: list[str] = []

        self._attr_unique_id = config[CONF_ID]
        self._set_attrs_from_config()

    def _set_attrs_from_config(self) -> None:
        """Set attributes from config."""
        self._attr_name = self._config[CONF_NAME]
        self._attr_entity_picture = self._config.get(CONF_PICTURE)
        self.device_trackers = self._config[CONF_DEVICE_TRACKERS]

    @classmethod
    def from_storage(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from storage."""
        person = cls(config)
        person.editable = True
        return person

    @classmethod
    def from_yaml(cls, config: ConfigType) -> Self:
        """Return entity instance initialized from yaml."""
        person = cls(config)
        person.editable = False
        return person

    async def async_added_to_hass(self) -> None:
        """Register device trackers."""
        await super().async_added_to_hass()
        if state := await self.async_get_last_state():
            self._parse_source_state(state)

        if self.hass.is_running:
            # Update person now if hass is already running.
            self._async_update_config(self._config)
        else:
            # Wait for hass start to not have race between person
            # and device trackers finishing setup.
            @callback
            def _async_person_start_hass(_: Event) -> None:
                self._async_update_config(self._config)

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, _async_person_start_hass
            )
            # Update extra state attributes now
            # as there are attributes that can already be set
            self._update_extra_state_attributes()

    async def async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._async_update_config(config)

    @callback
    def _async_update_config(self, config: ConfigType) -> None:
        """Handle when the config is updated."""
        self._config = config
        self._set_attrs_from_config()

        if self._unsub_track_device is not None:
            self._unsub_track_device()
            self._unsub_track_device = None

        if trackers := self._config[CONF_DEVICE_TRACKERS]:
            _LOGGER.debug("Subscribe to device trackers for %s", self.entity_id)

            self._unsub_track_device = async_track_state_change_event(
                self.hass, trackers, self._async_handle_tracker_update
            )

        self._update_state()

    @callback
    def _async_handle_tracker_update(self, event: Event[EventStateChangedData]) -> None:
        """Handle the device tracker state changes."""
        self._update_state()

    @callback
    def _update_state(self) -> None:
        """Update the state."""
        latest_non_gps_home = latest_not_home = latest_gps = latest = None
        for entity_id in self._config[CONF_DEVICE_TRACKERS]:
            state = self.hass.states.get(entity_id)

            if not state or state.state in IGNORE_STATES:
                continue

            if state.attributes.get(ATTR_SOURCE_TYPE) == SourceType.GPS:
                latest_gps = _get_latest(latest_gps, state)
            elif state.state == STATE_HOME:
                latest_non_gps_home = _get_latest(latest_non_gps_home, state)
            elif state.state == STATE_NOT_HOME:
                latest_not_home = _get_latest(latest_not_home, state)

        if latest_non_gps_home:
            home_zone = self.hass.states.get(ENTITY_ID_HOME)
            if home_zone and (
                latest_non_gps_home.attributes.get(ATTR_LATITUDE) is None
                and latest_non_gps_home.attributes.get(ATTR_LONGITUDE) is None
            ):
                latest = State(
                    latest_non_gps_home.entity_id,
                    latest_non_gps_home.state,
                    {
                        **latest_non_gps_home.attributes,
                        ATTR_LATITUDE: home_zone.attributes.get(ATTR_LATITUDE),
                        ATTR_LONGITUDE: home_zone.attributes.get(ATTR_LONGITUDE),
                    },
                    latest_non_gps_home.last_updated,
                )
            else:
                latest = latest_non_gps_home
        elif latest_gps:
            latest = latest_gps
        else:
            latest = latest_not_home

        if latest:
            self._parse_source_state(latest)
        else:
            self._attr_state = None
            self._source = None
            self._latitude = None
            self._longitude = None
            self._gps_accuracy = None

        self._update_extra_state_attributes()
        self.async_write_ha_state()

    @callback
    def _parse_source_state(self, state: State) -> None:
        """Parse source state and set person attributes.

        This is a device tracker state or the restored person state.
        """
        self._attr_state = state.state
        self._source = state.entity_id
        self._latitude = state.attributes.get(ATTR_LATITUDE)
        self._longitude = state.attributes.get(ATTR_LONGITUDE)
        self._gps_accuracy = state.attributes.get(ATTR_GPS_ACCURACY)

    @callback
    def _update_extra_state_attributes(self) -> None:
        """Update extra state attributes."""
        data: dict[str, Any] = {
            ATTR_EDITABLE: self.editable,
            ATTR_ID: self.unique_id,
            ATTR_DEVICE_TRACKERS: self.device_trackers,
        }

        if self._latitude is not None:
            data[ATTR_LATITUDE] = self._latitude
        if self._longitude is not None:
            data[ATTR_LONGITUDE] = self._longitude
        if self._gps_accuracy is not None:
            data[ATTR_GPS_ACCURACY] = self._gps_accuracy
        if self._source is not None:
            data[ATTR_SOURCE] = self._source
        if (user_id := self._config.get(CONF_USER_ID)) is not None:
            data[ATTR_USER_ID] = user_id

        self._attr_extra_state_attributes = data


def _get_latest(prev: State | None, curr: State) -> State:
    """Get latest state."""
    if prev is None or curr.last_updated > prev.last_updated:
        return curr
    return prev
