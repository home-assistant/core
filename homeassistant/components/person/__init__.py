"""Support for tracking people."""
import logging
from typing import List, Optional, cast

import voluptuous as vol

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.components import websocket_api
from homeassistant.components.device_tracker import (
    ATTR_SOURCE_TYPE,
    DOMAIN as DEVICE_TRACKER_DOMAIN,
    SOURCE_TYPE_GPS,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_ENTITY_ID,
    ATTR_GPS_ACCURACY,
    ATTR_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_NAME,
    CONF_ID,
    CONF_NAME,
    CONF_TYPE,
    EVENT_HOMEASSISTANT_START,
    SERVICE_RELOAD,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import (
    Event,
    HomeAssistant,
    ServiceCall,
    State,
    callback,
    split_entity_id,
)
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity_registry,
    service,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.loader import bind_hass

_LOGGER = logging.getLogger(__name__)

ATTR_SOURCE = "source"
ATTR_USER_ID = "user_id"

CONF_DEVICE_TRACKERS = "device_trackers"
CONF_USER_ID = "user_id"
CONF_PICTURE = "picture"

DOMAIN = "person"

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
async def async_create_person(hass, name, *, user_id=None, device_trackers=None):
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
):
    """Add a device tracker to a person linked to a user."""
    coll = cast(PersonStorageCollection, hass.data[DOMAIN][1])

    for person in coll.async_items():
        if person.get(ATTR_USER_ID) != user_id:
            continue

        device_trackers = person[CONF_DEVICE_TRACKERS]

        if device_tracker_entity_id in device_trackers:
            return

        await coll.async_update_item(
            person[collection.CONF_ID],
            {CONF_DEVICE_TRACKERS: device_trackers + [device_tracker_entity_id]},
        )
        break


CREATE_FIELDS = {
    vol.Required(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_USER_ID): vol.Any(str, None),
    vol.Optional(CONF_DEVICE_TRACKERS, default=list): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    vol.Optional(CONF_PICTURE): vol.Any(str, None),
}


UPDATE_FIELDS = {
    vol.Optional(CONF_NAME): vol.All(str, vol.Length(min=1)),
    vol.Optional(CONF_USER_ID): vol.Any(str, None),
    vol.Optional(CONF_DEVICE_TRACKERS, default=list): vol.All(
        cv.ensure_list, cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    vol.Optional(CONF_PICTURE): vol.Any(str, None),
}


class PersonStore(Store):
    """Person storage."""

    async def _async_migrate_func(self, old_version, old_data):
        """Migrate to the new version.

        Migrate storage to use format of collection helper.
        """
        return {"items": old_data["persons"]}


class PersonStorageCollection(collection.StorageCollection):
    """Person collection stored in storage."""

    CREATE_SCHEMA = vol.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = vol.Schema(UPDATE_FIELDS)

    def __init__(
        self,
        store: Store,
        logger: logging.Logger,
        id_manager: collection.IDManager,
        yaml_collection: collection.YamlCollection,
    ):
        """Initialize a person storage collection."""
        super().__init__(store, logger, id_manager)
        self.yaml_collection = yaml_collection

    async def _async_load_data(self) -> Optional[dict]:
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
            entity_registry.EVENT_ENTITY_REGISTRY_UPDATED, self._entity_registry_updated
        )

    async def _entity_registry_updated(self, event) -> None:
        """Handle entity registry updated."""
        if event.data["action"] != "remove":
            return

        entity_id = event.data[ATTR_ENTITY_ID]

        if split_entity_id(entity_id)[0] != "device_tracker":
            return

        for person in list(self.data.values()):
            if entity_id not in person[CONF_DEVICE_TRACKERS]:
                continue

            await self.async_update_item(
                person[collection.CONF_ID],
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

        user_id = data.get(CONF_USER_ID)

        if user_id is not None:
            await self._validate_user_id(user_id)

        return data

    @callback
    def _get_suggested_id(self, info: dict) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    async def _update_data(self, data: dict, update_data: dict) -> dict:
        """Return a new updated data object."""
        update_data = self.UPDATE_SCHEMA(update_data)

        user_id = update_data.get(CONF_USER_ID)

        if user_id is not None and user_id != data.get(CONF_USER_ID):
            await self._validate_user_id(user_id)

        return {**data, **update_data}

    async def _validate_user_id(self, user_id):
        """Validate the used user_id."""
        if await self.hass.auth.async_get_user(user_id) is None:
            raise ValueError("User does not exist")

        for persons in (self.data.values(), self.yaml_collection.async_items()):
            if any(person for person in persons if person.get(CONF_USER_ID) == user_id):
                raise ValueError("User already taken")


async def filter_yaml_data(hass: HomeAssistantType, persons: List[dict]) -> List[dict]:
    """Validate YAML data that we can't validate via schema."""
    filtered = []
    person_invalid_user = []

    for person_conf in persons:
        user_id = person_conf.get(CONF_USER_ID)

        if user_id is not None:
            if await hass.auth.async_get_user(user_id) is None:
                _LOGGER.error(
                    "Invalid user_id detected for person %s",
                    person_conf[collection.CONF_ID],
                )
                person_invalid_user.append(
                    f"- Person {person_conf[CONF_NAME]} (id: {person_conf[collection.CONF_ID]}) points at invalid user {user_id}"
                )
                continue

        filtered.append(person_conf)

    if person_invalid_user:
        hass.components.persistent_notification.async_create(
            f"""
The following persons point at invalid users:

{"- ".join(person_invalid_user)}
            """,
            "Invalid Person Configuration",
            DOMAIN,
        )

    return filtered


async def async_setup(hass: HomeAssistantType, config: ConfigType):
    """Set up the person component."""
    entity_component = EntityComponent(_LOGGER, DOMAIN, hass)
    id_manager = collection.IDManager()
    yaml_collection = collection.YamlCollection(
        logging.getLogger(f"{__name__}.yaml_collection"), id_manager
    )
    storage_collection = PersonStorageCollection(
        PersonStore(hass, STORAGE_VERSION, STORAGE_KEY),
        logging.getLogger(f"{__name__}.storage_collection"),
        id_manager,
        yaml_collection,
    )

    collection.attach_entity_component_collection(
        entity_component, yaml_collection, lambda conf: Person(conf, False)
    )
    collection.attach_entity_component_collection(
        entity_component, storage_collection, lambda conf: Person(conf, True)
    )
    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, yaml_collection)
    collection.attach_entity_registry_cleaner(hass, DOMAIN, DOMAIN, storage_collection)

    await yaml_collection.async_load(
        await filter_yaml_data(hass, config.get(DOMAIN, []))
    )
    await storage_collection.async_load()

    hass.data[DOMAIN] = (yaml_collection, storage_collection)

    collection.StorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass, create_list=False)

    websocket_api.async_register_command(hass, ws_list_person)

    async def _handle_user_removed(event: Event) -> None:
        """Handle a user being removed."""
        user_id = event.data[ATTR_USER_ID]
        for person in storage_collection.async_items():
            if person[CONF_USER_ID] == user_id:
                await storage_collection.async_update_item(
                    person[CONF_ID], {CONF_USER_ID: None}
                )

    hass.bus.async_listen(EVENT_USER_REMOVED, _handle_user_removed)

    async def async_reload_yaml(call: ServiceCall):
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


class Person(RestoreEntity):
    """Represent a tracked person."""

    def __init__(self, config, editable):
        """Set up person."""
        self._config = config
        self._editable = editable
        self._latitude = None
        self._longitude = None
        self._gps_accuracy = None
        self._source = None
        self._state = None
        self._unsub_track_device = None

    @property
    def name(self):
        """Return the name of the entity."""
        return self._config[CONF_NAME]

    @property
    def entity_picture(self) -> Optional[str]:
        """Return entity picture."""
        return self._config.get(CONF_PICTURE)

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return False

    @property
    def state(self):
        """Return the state of the person."""
        return self._state

    @property
    def state_attributes(self):
        """Return the state attributes of the person."""
        data = {ATTR_EDITABLE: self._editable, ATTR_ID: self.unique_id}
        if self._latitude is not None:
            data[ATTR_LATITUDE] = self._latitude
        if self._longitude is not None:
            data[ATTR_LONGITUDE] = self._longitude
        if self._gps_accuracy is not None:
            data[ATTR_GPS_ACCURACY] = self._gps_accuracy
        if self._source is not None:
            data[ATTR_SOURCE] = self._source
        user_id = self._config.get(CONF_USER_ID)
        if user_id is not None:
            data[ATTR_USER_ID] = user_id
        return data

    @property
    def unique_id(self):
        """Return a unique ID for the person."""
        return self._config[CONF_ID]

    async def async_added_to_hass(self):
        """Register device trackers."""
        await super().async_added_to_hass()
        state = await self.async_get_last_state()
        if state:
            self._parse_source_state(state)

        if self.hass.is_running:
            # Update person now if hass is already running.
            await self.async_update_config(self._config)
        else:
            # Wait for hass start to not have race between person
            # and device trackers finishing setup.
            async def person_start_hass(now):
                await self.async_update_config(self._config)

            self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_START, person_start_hass
            )

    async def async_update_config(self, config):
        """Handle when the config is updated."""
        self._config = config

        if self._unsub_track_device is not None:
            self._unsub_track_device()
            self._unsub_track_device = None

        trackers = self._config[CONF_DEVICE_TRACKERS]

        if trackers:
            _LOGGER.debug("Subscribe to device trackers for %s", self.entity_id)

            self._unsub_track_device = async_track_state_change_event(
                self.hass, trackers, self._async_handle_tracker_update
            )

        self._update_state()

    @callback
    def _async_handle_tracker_update(self, event):
        """Handle the device tracker state changes."""
        self._update_state()

    @callback
    def _update_state(self):
        """Update the state."""
        latest_non_gps_home = latest_not_home = latest_gps = latest = None
        for entity_id in self._config[CONF_DEVICE_TRACKERS]:
            state = self.hass.states.get(entity_id)

            if not state or state.state in IGNORE_STATES:
                continue

            if state.attributes.get(ATTR_SOURCE_TYPE) == SOURCE_TYPE_GPS:
                latest_gps = _get_latest(latest_gps, state)
            elif state.state == STATE_HOME:
                latest_non_gps_home = _get_latest(latest_non_gps_home, state)
            elif state.state == STATE_NOT_HOME:
                latest_not_home = _get_latest(latest_not_home, state)

        if latest_non_gps_home:
            latest = latest_non_gps_home
        elif latest_gps:
            latest = latest_gps
        else:
            latest = latest_not_home

        if latest:
            self._parse_source_state(latest)
        else:
            self._state = None
            self._source = None
            self._latitude = None
            self._longitude = None
            self._gps_accuracy = None

        self.async_write_ha_state()

    @callback
    def _parse_source_state(self, state):
        """Parse source state and set person attributes.

        This is a device tracker state or the restored person state.
        """
        self._state = state.state
        self._source = state.entity_id
        self._latitude = state.attributes.get(ATTR_LATITUDE)
        self._longitude = state.attributes.get(ATTR_LONGITUDE)
        self._gps_accuracy = state.attributes.get(ATTR_GPS_ACCURACY)


@websocket_api.websocket_command({vol.Required(CONF_TYPE): "person/list"})
def ws_list_person(
    hass: HomeAssistantType, connection: websocket_api.ActiveConnection, msg
):
    """List persons."""
    yaml, storage = hass.data[DOMAIN]
    connection.send_result(
        msg[ATTR_ID], {"storage": storage.async_items(), "config": yaml.async_items()}
    )


def _get_latest(prev: Optional[State], curr: State):
    """Get latest state."""
    if prev is None or curr.last_updated > prev.last_updated:
        return curr
    return prev
