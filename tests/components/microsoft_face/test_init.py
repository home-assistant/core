"""The tests for the microsoft face platform."""
import asyncio
from unittest.mock import patch

import pytest

from homeassistant.components import camera, microsoft_face as mf
from homeassistant.components.microsoft_face import (
    ATTR_CAMERA_ENTITY,
    ATTR_GROUP,
    ATTR_PERSON,
    DOMAIN,
    SERVICE_CREATE_GROUP,
    SERVICE_CREATE_PERSON,
    SERVICE_DELETE_GROUP,
    SERVICE_DELETE_PERSON,
    SERVICE_FACE_PERSON,
    SERVICE_TRAIN_GROUP,
)
from homeassistant.const import ATTR_NAME
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, load_fixture


def create_group(hass, name):
    """Create a new person group.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_NAME: name}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_CREATE_GROUP, data))


def delete_group(hass, name):
    """Delete a person group.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_NAME: name}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_DELETE_GROUP, data))


def train_group(hass, group):
    """Train a person group.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_GROUP: group}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_TRAIN_GROUP, data))


def create_person(hass, group, name):
    """Create a person in a group.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_GROUP: group, ATTR_NAME: name}
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_CREATE_PERSON, data)
    )


def delete_person(hass, group, name):
    """Delete a person in a group.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_GROUP: group, ATTR_NAME: name}
    hass.async_create_task(
        hass.services.async_call(DOMAIN, SERVICE_DELETE_PERSON, data)
    )


def face_person(hass, group, person, camera_entity):
    """Add a new face picture to a person.

    This is a legacy helper method. Do not use it for new tests.
    """
    data = {ATTR_GROUP: group, ATTR_PERSON: person, ATTR_CAMERA_ENTITY: camera_entity}
    hass.async_create_task(hass.services.async_call(DOMAIN, SERVICE_FACE_PERSON, data))


CONFIG = {mf.DOMAIN: {"api_key": "12345678abcdef"}}
ENDPOINT_URL = f"https://westus.{mf.FACE_API_URL}"


@pytest.fixture
def mock_update():
    """Mock update store."""
    with patch(
        "homeassistant.components.microsoft_face.MicrosoftFace.update_store",
        return_value=None,
    ) as mock_update_store:
        yield mock_update_store


async def test_setup_component(hass, mock_update):
    """Set up component."""
    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)


async def test_setup_component_wrong_api_key(hass, mock_update):
    """Set up component without api key."""
    with assert_setup_component(0, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, {mf.DOMAIN: {}})


async def test_setup_component_test_service(hass, mock_update):
    """Set up component."""
    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    assert hass.services.has_service(mf.DOMAIN, "create_group")
    assert hass.services.has_service(mf.DOMAIN, "delete_group")
    assert hass.services.has_service(mf.DOMAIN, "train_group")
    assert hass.services.has_service(mf.DOMAIN, "create_person")
    assert hass.services.has_service(mf.DOMAIN, "delete_person")
    assert hass.services.has_service(mf.DOMAIN, "face_person")


async def test_setup_component_test_entities(hass, aioclient_mock):
    """Set up component."""
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups"),
        text=load_fixture("microsoft_face_persongroups.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group1/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group2/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )

    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    assert len(aioclient_mock.mock_calls) == 3

    entity_group1 = hass.states.get("microsoft_face.test_group1")
    entity_group2 = hass.states.get("microsoft_face.test_group2")

    assert entity_group1 is not None
    assert entity_group2 is not None

    assert entity_group1.attributes["Ryan"] == "25985303-c537-4467-b41d-bdb45cd95ca1"
    assert entity_group1.attributes["David"] == "2ae4935b-9659-44c3-977f-61fac20d0538"

    assert entity_group2.attributes["Ryan"] == "25985303-c537-4467-b41d-bdb45cd95ca1"
    assert entity_group2.attributes["David"] == "2ae4935b-9659-44c3-977f-61fac20d0538"


async def test_service_groups(hass, mock_update, aioclient_mock):
    """Set up component, test groups services."""
    aioclient_mock.put(
        ENDPOINT_URL.format("persongroups/service_group"),
        status=200,
        text="{}",
    )
    aioclient_mock.delete(
        ENDPOINT_URL.format("persongroups/service_group"),
        status=200,
        text="{}",
    )

    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    create_group(hass, "Service Group")
    await hass.async_block_till_done()

    entity = hass.states.get("microsoft_face.service_group")
    assert entity is not None
    assert len(aioclient_mock.mock_calls) == 1

    delete_group(hass, "Service Group")
    await hass.async_block_till_done()

    entity = hass.states.get("microsoft_face.service_group")
    assert entity is None
    assert len(aioclient_mock.mock_calls) == 2


async def test_service_person(hass, aioclient_mock):
    """Set up component, test person services."""
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups"),
        text=load_fixture("microsoft_face_persongroups.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group1/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group2/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )

    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    assert len(aioclient_mock.mock_calls) == 3

    aioclient_mock.post(
        ENDPOINT_URL.format("persongroups/test_group1/persons"),
        text=load_fixture("microsoft_face_create_person.json"),
    )
    aioclient_mock.delete(
        ENDPOINT_URL.format(
            "persongroups/test_group1/persons/25985303-c537-4467-b41d-bdb45cd95ca1"
        ),
        status=200,
        text="{}",
    )

    create_person(hass, "test group1", "Hans")
    await hass.async_block_till_done()

    entity_group1 = hass.states.get("microsoft_face.test_group1")

    assert len(aioclient_mock.mock_calls) == 4
    assert entity_group1 is not None
    assert entity_group1.attributes["Hans"] == "25985303-c537-4467-b41d-bdb45cd95ca1"

    delete_person(hass, "test group1", "Hans")
    await hass.async_block_till_done()

    entity_group1 = hass.states.get("microsoft_face.test_group1")

    assert len(aioclient_mock.mock_calls) == 5
    assert entity_group1 is not None
    assert "Hans" not in entity_group1.attributes


async def test_service_train(hass, mock_update, aioclient_mock):
    """Set up component, test train groups services."""
    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    aioclient_mock.post(
        ENDPOINT_URL.format("persongroups/service_group/train"),
        status=200,
        text="{}",
    )

    train_group(hass, "Service Group")
    await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1


async def test_service_face(hass, aioclient_mock):
    """Set up component, test person face services."""
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups"),
        text=load_fixture("microsoft_face_persongroups.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group1/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group2/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )

    CONFIG["camera"] = {"platform": "demo"}
    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    assert len(aioclient_mock.mock_calls) == 3

    aioclient_mock.post(
        ENDPOINT_URL.format(
            "persongroups/test_group2/persons/"
            "2ae4935b-9659-44c3-977f-61fac20d0538/persistedFaces"
        ),
        status=200,
        text="{}",
    )

    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"Test"),
    ):
        face_person(hass, "test_group2", "David", "camera.demo_camera")
        await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 4
    assert aioclient_mock.mock_calls[3][2] == b"Test"


async def test_service_status_400(hass, mock_update, aioclient_mock):
    """Set up component, test groups services with error."""
    aioclient_mock.put(
        ENDPOINT_URL.format("persongroups/service_group"),
        status=400,
        text="{'error': {'message': 'Error'}}",
    )

    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    create_group(hass, "Service Group")
    await hass.async_block_till_done()

    entity = hass.states.get("microsoft_face.service_group")
    assert entity is None
    assert len(aioclient_mock.mock_calls) == 1


async def test_service_status_timeout(hass, mock_update, aioclient_mock):
    """Set up component, test groups services with timeout."""
    aioclient_mock.put(
        ENDPOINT_URL.format("persongroups/service_group"),
        status=400,
        exc=asyncio.TimeoutError(),
    )

    with assert_setup_component(3, mf.DOMAIN):
        await async_setup_component(hass, mf.DOMAIN, CONFIG)

    create_group(hass, "Service Group")
    await hass.async_block_till_done()

    entity = hass.states.get("microsoft_face.service_group")
    assert entity is None
    assert len(aioclient_mock.mock_calls) == 1
