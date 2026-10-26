"""Support for tracking people."""

from dataclasses import dataclass
import logging
import re
from typing import Any, override

import probatio

from homeassistant.auth import EVENT_USER_REMOVED
from homeassistant.components import websocket_api
from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.image_upload import (
    DOMAIN as IMAGE_UPLOAD_DOMAIN,
    ImageStorageCollection,
)
from homeassistant.const import ATTR_ID, ATTR_NAME, CONF_ID, CONF_NAME, SERVICE_RELOAD
from homeassistant.core import Event, HomeAssistant, callback, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    collection,
    config_validation as cv,
    entity_registry as er,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType, VolDictType

from .const import (
    CONF_DEVICE_TRACKERS,
    CONF_PICTURE,
    CONF_USER_ID,
    DATA_PERSON,
    DOMAIN,
    PersonEntityStateAttribute,
)
from .entity import Person
from .helpers import filter_yaml_data
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ATTR_USER_ID = "user_id"

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 2

# Pictures users set for themselves must be images uploaded to
# Home Assistant, so they cannot point other users' browsers elsewhere.
UPLOADED_PICTURE_RE = re.compile(
    r"^/api/image/serve/(?P<image_id>[0-9a-f]{32})/(original|\d+x\d+)$"
)

PERSON_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_ID): cv.string,
        probatio.Required(CONF_NAME): cv.string,
        probatio.Optional(CONF_USER_ID): cv.string,
        probatio.Optional(CONF_DEVICE_TRACKERS, default=[]): probatio.All(
            probatio.EnsureList(), cv.entities_domain(DEVICE_TRACKER_DOMAIN)
        ),
        probatio.Optional(CONF_PICTURE): cv.string,
    }
)

CONFIG_SCHEMA = probatio.Schema(
    {
        probatio.Optional(DOMAIN, default=[]): probatio.All(
            probatio.EnsureList(), cv.remove_falsy, [PERSON_SCHEMA]
        )
    },
    extra=probatio.ALLOW_EXTRA,
)

__all__ = [
    "ATTR_USER_ID",
    "DOMAIN",
    "SERVICE_RELOAD",
    "Person",
    "PersonEntityStateAttribute",
    "PersonStorageCollection",
    "async_add_user_device_tracker",
    "async_create_person",
    "entities_in_person",
    "persons_with_entity",
]


async def async_create_person(
    hass: HomeAssistant,
    name: str,
    *,
    user_id: str | None = None,
    device_trackers: list[str] | None = None,
) -> None:
    """Create a new person."""
    await hass.data[DATA_PERSON].storage_collection.async_create_item(
        {
            ATTR_NAME: name,
            ATTR_USER_ID: user_id,
            CONF_DEVICE_TRACKERS: device_trackers or [],
        }
    )


async def async_add_user_device_tracker(
    hass: HomeAssistant, user_id: str, device_tracker_entity_id: str
) -> None:
    """Add a device tracker to a person linked to a user."""
    coll = hass.data[DATA_PERSON].storage_collection

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

    component = hass.data[DATA_PERSON].entity_component

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

    component = hass.data[DATA_PERSON].entity_component

    if (person_entity := component.get_entity(entity_id)) is None:
        return []

    return person_entity.device_trackers


CREATE_FIELDS: VolDictType = {
    probatio.Required(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_USER_ID): probatio.Any(str, None),
    probatio.Optional(CONF_DEVICE_TRACKERS, default=list): probatio.All(
        probatio.EnsureList(), cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    probatio.Optional(CONF_PICTURE): probatio.Any(str, None),
}


UPDATE_FIELDS: VolDictType = {
    probatio.Optional(CONF_NAME): probatio.All(str, probatio.NonEmpty()),
    probatio.Optional(CONF_USER_ID): probatio.Any(str, None),
    probatio.Optional(CONF_DEVICE_TRACKERS, default=list): probatio.All(
        probatio.EnsureList(), cv.entities_domain(DEVICE_TRACKER_DOMAIN)
    ),
    probatio.Optional(CONF_PICTURE): probatio.Any(str, None),
}


class PersonStore(Store):
    """Person storage."""

    @override
    async def _async_migrate_func(
        self, old_major_version: int, old_minor_version: int, old_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Migrate to the new version.

        Migrate storage to use format of collection helper.
        """
        return {"items": old_data["persons"]}


class PersonStorageCollection(collection.DictStorageCollection):
    """Person collection stored in storage."""

    CREATE_SCHEMA = probatio.Schema(CREATE_FIELDS)
    UPDATE_SCHEMA = probatio.Schema(UPDATE_FIELDS)

    def __init__(
        self,
        store: Store,
        id_manager: collection.IDManager,
        yaml_collection: collection.YamlCollection,
    ) -> None:
        """Initialize a person storage collection."""
        super().__init__(store, id_manager)
        self.yaml_collection = yaml_collection

    @override
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

    @override
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

    @override
    async def _process_create_data(self, data: dict) -> dict:
        """Validate the config is valid."""
        data = self.CREATE_SCHEMA(data)

        if (user_id := data.get(CONF_USER_ID)) is not None:
            await self._validate_user_id(user_id)

        return data

    @callback
    @override
    def _get_suggested_id(self, info: dict[str, str]) -> str:
        """Suggest an ID based on the config."""
        return info[CONF_NAME]

    @override
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

    @override
    def ws_list_item(
        self,
        hass: HomeAssistant,
        connection: websocket_api.ActiveConnection,
        msg: dict[str, Any],
    ) -> None:
        """List persons."""
        data = hass.data[DATA_PERSON]
        connection.send_result(
            msg[ATTR_ID],
            {
                "storage": data.storage_collection.async_items(),
                "config": data.yaml_collection.async_items(),
            },
        )


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "person/update_own_profile",
        probatio.Optional(CONF_NAME): probatio.All(
            str, probatio.Strip, probatio.NonEmpty()
        ),
        probatio.Optional(CONF_PICTURE): probatio.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_own_profile(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Let a user update their own name and picture.

    Unlike the admin-only person/update, this only touches the name and
    picture of the calling user and the person linked to them.
    """
    user = connection.user
    if user.system_generated:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="system_generated_user",
        )

    data = hass.data[DATA_PERSON]
    yaml_collection = data.yaml_collection
    storage_collection = data.storage_collection

    person = next(
        (
            item
            for item in storage_collection.async_items()
            if item.get(CONF_USER_ID) == user.id
        ),
        None,
    )

    if CONF_PICTURE in msg:
        if person is None:
            translation_key = "no_person_linked"
            if any(
                item.get(CONF_USER_ID) == user.id
                for item in yaml_collection.async_items()
            ):
                translation_key = "person_not_editable"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
            )
        _validate_own_picture(hass, msg[CONF_PICTURE])

    if CONF_NAME in msg and msg[CONF_NAME] != user.name:
        await hass.auth.async_update_user(user, name=msg[CONF_NAME])

    if person is not None:
        updates = {key: msg[key] for key in (CONF_NAME, CONF_PICTURE) if key in msg}
        if updates:
            # Pass the device trackers along, as the update schema
            # would otherwise reset them to an empty list.
            person = await storage_collection.async_update_item(
                person[CONF_ID],
                {**updates, CONF_DEVICE_TRACKERS: person[CONF_DEVICE_TRACKERS]},
            )

    connection.send_result(msg[ATTR_ID], {"user_name": user.name, "person": person})


@callback
def _validate_own_picture(hass: HomeAssistant, picture: str | None) -> None:
    """Validate a picture is one uploaded to Home Assistant."""
    if picture is None:
        return
    images: ImageStorageCollection = hass.data[IMAGE_UPLOAD_DOMAIN]
    match = UPLOADED_PICTURE_RE.match(picture)
    if match is None or match.group("image_id") not in images.data:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="invalid_picture",
        )


@dataclass(slots=True)
class PersonData:
    """Runtime data for the person integration."""

    entity_component: EntityComponent[Person]
    storage_collection: PersonStorageCollection
    yaml_collection: collection.YamlCollection


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

    hass.data[DATA_PERSON] = PersonData(
        entity_component, storage_collection, yaml_collection
    )

    PersonStorageCollectionWebsocket(
        storage_collection, DOMAIN, DOMAIN, CREATE_FIELDS, UPDATE_FIELDS
    ).async_setup(hass)
    websocket_api.async_register_command(hass, ws_update_own_profile)

    async def _handle_user_removed(event: Event) -> None:
        """Handle a user being removed."""
        user_id = event.data[ATTR_USER_ID]
        for person in storage_collection.async_items():
            if person[CONF_USER_ID] == user_id:
                await storage_collection.async_update_item(
                    person[CONF_ID], {CONF_USER_ID: None}
                )

    hass.bus.async_listen(EVENT_USER_REMOVED, _handle_user_removed)

    async_setup_services(hass)

    return True
