"""Support for Microsoft face recognition."""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
import json
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import CONTENT_TYPE
import voluptuous as vol

from homeassistant.components import camera
from homeassistant.const import ATTR_NAME, CONF_API_KEY, CONF_TIMEOUT, CONTENT_TYPE_JSON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)

ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_GROUP = "group"
ATTR_PERSON = "person"

CONF_AZURE_REGION = "azure_region"

DATA_MICROSOFT_FACE = "microsoft_face"
DEFAULT_TIMEOUT = 10
DOMAIN = "microsoft_face"

FACE_API_URL = "api.cognitive.microsoft.com/face/v1.0/{0}"

SERVICE_CREATE_GROUP = "create_group"
SERVICE_CREATE_PERSON = "create_person"
SERVICE_DELETE_GROUP = "delete_group"
SERVICE_DELETE_PERSON = "delete_person"
SERVICE_FACE_PERSON = "face_person"
SERVICE_TRAIN_GROUP = "train_group"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_AZURE_REGION, default="westus"): cv.string,
                vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SCHEMA_GROUP_SERVICE = vol.Schema({vol.Required(ATTR_NAME): cv.string})

SCHEMA_PERSON_SERVICE = SCHEMA_GROUP_SERVICE.extend(
    {vol.Required(ATTR_GROUP): cv.slugify}
)

SCHEMA_FACE_SERVICE = vol.Schema(
    {
        vol.Required(ATTR_PERSON): cv.string,
        vol.Required(ATTR_GROUP): cv.slugify,
        vol.Required(ATTR_CAMERA_ENTITY): cv.entity_id,
    }
)

SCHEMA_TRAIN_SERVICE = vol.Schema({vol.Required(ATTR_GROUP): cv.slugify})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Microsoft Face."""
    component = EntityComponent[MicrosoftFaceGroupEntity](
        logging.getLogger(__name__), DOMAIN, hass
    )
    entities: dict[str, MicrosoftFaceGroupEntity] = {}
    face = MicrosoftFace(
        hass,
        config[DOMAIN].get(CONF_AZURE_REGION),
        config[DOMAIN].get(CONF_API_KEY),
        config[DOMAIN].get(CONF_TIMEOUT),
        component,
        entities,
    )

    try:
        # read exists group/person from cloud and create entities
        await face.update_store()
    except HomeAssistantError as err:
        _LOGGER.error("Can't load data from face api: %s", err)
        return False

    hass.data[DATA_MICROSOFT_FACE] = face

    async def async_create_group(service: ServiceCall) -> None:
        """Create a new person group."""
        name = service.data[ATTR_NAME]
        g_id = slugify(name)

        try:
            await face.call_api("put", f"persongroups/{g_id}", {"name": name})
            face.store[g_id] = {}
            old_entity = entities.pop(g_id, None)
            if old_entity:
                await component.async_remove_entity(old_entity.entity_id)

            entities[g_id] = MicrosoftFaceGroupEntity(hass, face, g_id, name)
            await component.async_add_entities([entities[g_id]])
        except HomeAssistantError as err:
            _LOGGER.error("Can't create group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_GROUP, async_create_group, schema=SCHEMA_GROUP_SERVICE
    )

    async def async_delete_group(service: ServiceCall) -> None:
        """Delete a person group."""
        g_id = slugify(service.data[ATTR_NAME])

        try:
            await face.call_api("delete", f"persongroups/{g_id}")
            face.store.pop(g_id)

            entity = entities.pop(g_id)
            await component.async_remove_entity(entity.entity_id)
        except HomeAssistantError as err:
            _LOGGER.error("Can't delete group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_GROUP, async_delete_group, schema=SCHEMA_GROUP_SERVICE
    )

    async def async_train_group(service: ServiceCall) -> None:
        """Train a person group."""
        g_id = service.data[ATTR_GROUP]

        try:
            await face.call_api("post", f"persongroups/{g_id}/train")
        except HomeAssistantError as err:
            _LOGGER.error("Can't train group '%s' with error: %s", g_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_TRAIN_GROUP, async_train_group, schema=SCHEMA_TRAIN_SERVICE
    )

    async def async_create_person(service: ServiceCall) -> None:
        """Create a person in a group."""
        name = service.data[ATTR_NAME]
        g_id = service.data[ATTR_GROUP]

        try:
            user_data = await face.call_api(
                "post", f"persongroups/{g_id}/persons", {"name": name}
            )

            face.store[g_id][name] = user_data["personId"]
            entities[g_id].async_write_ha_state()
        except HomeAssistantError as err:
            _LOGGER.error("Can't create person '%s' with error: %s", name, err)

    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_PERSON, async_create_person, schema=SCHEMA_PERSON_SERVICE
    )

    async def async_delete_person(service: ServiceCall) -> None:
        """Delete a person in a group."""
        name = service.data[ATTR_NAME]
        g_id = service.data[ATTR_GROUP]
        p_id = face.store[g_id].get(name)

        try:
            await face.call_api("delete", f"persongroups/{g_id}/persons/{p_id}")

            face.store[g_id].pop(name)
            entities[g_id].async_write_ha_state()
        except HomeAssistantError as err:
            _LOGGER.error("Can't delete person '%s' with error: %s", p_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_PERSON, async_delete_person, schema=SCHEMA_PERSON_SERVICE
    )

    async def async_face_person(service: ServiceCall) -> None:
        """Add a new face picture to a person."""
        g_id = service.data[ATTR_GROUP]
        p_id = face.store[g_id].get(service.data[ATTR_PERSON])

        camera_entity = service.data[ATTR_CAMERA_ENTITY]

        try:
            image = await camera.async_get_image(hass, camera_entity)

            await face.call_api(
                "post",
                f"persongroups/{g_id}/persons/{p_id}/persistedFaces",
                image.content,
                binary=True,
            )
        except HomeAssistantError as err:
            _LOGGER.error(
                "Can't add an image of a person '%s' with error: %s", p_id, err
            )

    hass.services.async_register(
        DOMAIN, SERVICE_FACE_PERSON, async_face_person, schema=SCHEMA_FACE_SERVICE
    )

    return True


class MicrosoftFaceGroupEntity(Entity):
    """Person-Group state/data Entity."""

    _attr_should_poll = False

    def __init__(self, hass, api, g_id, name):
        """Initialize person/group entity."""
        self.hass = hass
        self._api = api
        self._id = g_id
        self._name = name

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def entity_id(self):
        """Return entity id."""
        return f"{DOMAIN}.{self._id}"

    @property
    def state(self):
        """Return the state of the entity."""
        return len(self._api.store[self._id])

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return dict(self._api.store[self._id])


class MicrosoftFace:
    """Microsoft Face api for Home Assistant."""

    def __init__(self, hass, server_loc, api_key, timeout, component, entities):
        """Initialize Microsoft Face api."""
        self.hass = hass
        self.websession = async_get_clientsession(hass)
        self.timeout = timeout
        self._api_key = api_key
        self._server_url = f"https://{server_loc}.{FACE_API_URL}"
        self._store = {}
        self._component: EntityComponent[MicrosoftFaceGroupEntity] = component
        self._entities = entities

    @property
    def store(self):
        """Store group/person data and IDs."""
        return self._store

    async def update_store(self) -> None:
        """Load all group/person data into local store."""
        groups = await self.call_api("get", "persongroups")

        remove_tasks: list[Coroutine[Any, Any, None]] = []
        new_entities = []
        for group in groups:
            g_id = group["personGroupId"]
            self._store[g_id] = {}
            old_entity = self._entities.pop(g_id, None)
            if old_entity:
                remove_tasks.append(
                    self._component.async_remove_entity(old_entity.entity_id)
                )

            self._entities[g_id] = MicrosoftFaceGroupEntity(
                self.hass, self, g_id, group["name"]
            )
            new_entities.append(self._entities[g_id])

            persons = await self.call_api("get", f"persongroups/{g_id}/persons")

            for person in persons:
                self._store[g_id][person["name"]] = person["personId"]

        if remove_tasks:
            await asyncio.gather(*remove_tasks)
        await self._component.async_add_entities(new_entities)

    async def call_api(self, method, function, data=None, binary=False, params=None):
        """Make an api call."""
        headers = {"Ocp-Apim-Subscription-Key": self._api_key}
        url = self._server_url.format(function)

        payload = None
        if binary:
            headers[CONTENT_TYPE] = "application/octet-stream"
            payload = data
        else:
            headers[CONTENT_TYPE] = CONTENT_TYPE_JSON
            if data is not None:
                payload = json.dumps(data).encode()
            else:
                payload = None

        try:
            async with asyncio.timeout(self.timeout):
                response = await getattr(self.websession, method)(
                    url, data=payload, headers=headers, params=params
                )

                answer = await response.json()

            _LOGGER.debug("Read from microsoft face api: %s", answer)
            if response.status < 300:
                return answer

            _LOGGER.warning(
                "Error %d microsoft face api %s", response.status, response.url
            )
            raise HomeAssistantError(answer["error"]["message"])

        except aiohttp.ClientError:
            _LOGGER.warning("Can't connect to microsoft face api")

        except TimeoutError:
            _LOGGER.warning("Timeout from microsoft face api %s", response.url)

        raise HomeAssistantError("Network error on microsoft face api.")
