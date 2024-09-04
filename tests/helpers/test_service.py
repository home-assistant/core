"""Test service helpers."""

import asyncio
from collections.abc import Iterable
from copy import deepcopy
import io
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from pytest_unordered import unordered
import voluptuous as vol

# To prevent circular import when running just this file
from homeassistant import exceptions
from homeassistant.auth.permissions import PolicyPermissions
import homeassistant.components  # noqa: F401
from homeassistant.components.group import DOMAIN as DOMAIN_GROUP, Group
from homeassistant.components.logger import DOMAIN as DOMAIN_LOGGER
from homeassistant.components.shell_command import DOMAIN as DOMAIN_SHELL_COMMAND
from homeassistant.components.system_health import DOMAIN as DOMAIN_SYSTEM_HEALTH
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import (
    Context,
    HassJob,
    HomeAssistant,
    ServiceCall,
    SupportsResponse,
)
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    service,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_setup_component
from homeassistant.util.yaml.loader import parse_yaml

from tests.common import (
    MockEntity,
    MockModule,
    MockUser,
    async_mock_service,
    mock_area_registry,
    mock_device_registry,
    mock_integration,
    mock_registry,
)

SUPPORT_A = 1
SUPPORT_B = 2
SUPPORT_C = 4


@pytest.fixture
def mock_handle_entity_call():
    """Mock service platform call."""
    with patch(
        "homeassistant.helpers.service._handle_entity_call",
        return_value=None,
    ) as mock_call:
        yield mock_call


@pytest.fixture
def mock_entities(hass: HomeAssistant) -> dict[str, MockEntity]:
    """Return mock entities in an ordered dict."""
    kitchen = MockEntity(
        entity_id="light.kitchen",
        available=True,
        should_poll=False,
        supported_features=SUPPORT_A,
    )
    living_room = MockEntity(
        entity_id="light.living_room",
        available=True,
        should_poll=False,
        supported_features=SUPPORT_B,
    )
    bedroom = MockEntity(
        entity_id="light.bedroom",
        available=True,
        should_poll=False,
        supported_features=(SUPPORT_A | SUPPORT_B),
    )
    bathroom = MockEntity(
        entity_id="light.bathroom",
        available=True,
        should_poll=False,
        supported_features=(SUPPORT_B | SUPPORT_C),
    )
    entities = {}
    entities[kitchen.entity_id] = kitchen
    entities[living_room.entity_id] = living_room
    entities[bedroom.entity_id] = bedroom
    entities[bathroom.entity_id] = bathroom
    for entity in entities.values():
        entity.hass = hass
    return entities


@pytest.fixture
def floor_area_mock(hass: HomeAssistant) -> None:
    """Mock including floor and area info."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set("light.Kitchen", STATE_OFF)

    area_in_floor = ar.AreaEntry(
        id="test-area",
        name="Test area",
        aliases={},
        normalized_name="test-area",
        floor_id="test-floor",
        icon=None,
        picture=None,
    )
    area_in_floor_a = ar.AreaEntry(
        id="area-a",
        name="Area A",
        aliases={},
        normalized_name="area-a",
        floor_id="floor-a",
        icon=None,
        picture=None,
    )
    mock_area_registry(
        hass,
        {
            area_in_floor.id: area_in_floor,
            area_in_floor_a.id: area_in_floor_a,
        },
    )

    device_in_area = dr.DeviceEntry(area_id="test-area")
    device_no_area = dr.DeviceEntry(id="device-no-area-id")
    device_diff_area = dr.DeviceEntry(area_id="diff-area")
    device_area_a = dr.DeviceEntry(id="device-area-a-id", area_id="area-a")

    mock_device_registry(
        hass,
        {
            device_in_area.id: device_in_area,
            device_no_area.id: device_no_area,
            device_diff_area.id: device_diff_area,
            device_area_a.id: device_area_a,
        },
    )

    entity_in_own_area = er.RegistryEntry(
        entity_id="light.in_own_area",
        unique_id="in-own-area-id",
        platform="test",
        area_id="own-area",
    )
    config_entity_in_own_area = er.RegistryEntry(
        entity_id="light.config_in_own_area",
        unique_id="config-in-own-area-id",
        platform="test",
        area_id="own-area",
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_in_own_area = er.RegistryEntry(
        entity_id="light.hidden_in_own_area",
        unique_id="hidden-in-own-area-id",
        platform="test",
        area_id="own-area",
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_in_area = er.RegistryEntry(
        entity_id="light.in_area",
        unique_id="in-area-id",
        platform="test",
        device_id=device_in_area.id,
    )
    config_entity_in_area = er.RegistryEntry(
        entity_id="light.config_in_area",
        unique_id="config-in-area-id",
        platform="test",
        device_id=device_in_area.id,
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_in_area = er.RegistryEntry(
        entity_id="light.hidden_in_area",
        unique_id="hidden-in-area-id",
        platform="test",
        device_id=device_in_area.id,
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_in_other_area = er.RegistryEntry(
        entity_id="light.in_other_area",
        unique_id="in-area-a-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="other-area",
    )
    entity_assigned_to_area = er.RegistryEntry(
        entity_id="light.assigned_to_area",
        unique_id="assigned-area-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="test-area",
    )
    entity_no_area = er.RegistryEntry(
        entity_id="light.no_area",
        unique_id="no-area-id",
        platform="test",
        device_id=device_no_area.id,
    )
    config_entity_no_area = er.RegistryEntry(
        entity_id="light.config_no_area",
        unique_id="config-no-area-id",
        platform="test",
        device_id=device_no_area.id,
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_no_area = er.RegistryEntry(
        entity_id="light.hidden_no_area",
        unique_id="hidden-no-area-id",
        platform="test",
        device_id=device_no_area.id,
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_diff_area = er.RegistryEntry(
        entity_id="light.diff_area",
        unique_id="diff-area-id",
        platform="test",
        device_id=device_diff_area.id,
    )
    entity_in_area_a = er.RegistryEntry(
        entity_id="light.in_area_a",
        unique_id="in-area-a-id",
        platform="test",
        device_id=device_area_a.id,
        area_id="area-a",
    )
    entity_in_area_b = er.RegistryEntry(
        entity_id="light.in_area_b",
        unique_id="in-area-b-id",
        platform="test",
        device_id=device_area_a.id,
        area_id="area-b",
    )
    mock_registry(
        hass,
        {
            entity_in_own_area.entity_id: entity_in_own_area,
            config_entity_in_own_area.entity_id: config_entity_in_own_area,
            hidden_entity_in_own_area.entity_id: hidden_entity_in_own_area,
            entity_in_area.entity_id: entity_in_area,
            config_entity_in_area.entity_id: config_entity_in_area,
            hidden_entity_in_area.entity_id: hidden_entity_in_area,
            entity_in_other_area.entity_id: entity_in_other_area,
            entity_assigned_to_area.entity_id: entity_assigned_to_area,
            entity_no_area.entity_id: entity_no_area,
            config_entity_no_area.entity_id: config_entity_no_area,
            hidden_entity_no_area.entity_id: hidden_entity_no_area,
            entity_diff_area.entity_id: entity_diff_area,
            entity_in_area_a.entity_id: entity_in_area_a,
            entity_in_area_b.entity_id: entity_in_area_b,
        },
    )


@pytest.fixture
def label_mock(hass: HomeAssistant) -> None:
    """Mock including label info."""
    hass.states.async_set("light.bowl", STATE_ON)
    hass.states.async_set("light.ceiling", STATE_OFF)
    hass.states.async_set("light.kitchen", STATE_OFF)

    area_with_labels = ar.AreaEntry(
        id="area-with-labels",
        name="Area with labels",
        aliases={},
        normalized_name="with_labels",
        floor_id=None,
        icon=None,
        labels={"label_area"},
        picture=None,
    )
    area_without_labels = ar.AreaEntry(
        id="area-no-labels",
        name="Area without labels",
        aliases={},
        normalized_name="without_labels",
        floor_id=None,
        icon=None,
        labels=set(),
        picture=None,
    )
    mock_area_registry(
        hass,
        {
            area_with_labels.id: area_with_labels,
            area_without_labels.id: area_without_labels,
        },
    )

    device_has_label1 = dr.DeviceEntry(labels={"label1"})
    device_has_label2 = dr.DeviceEntry(labels={"label2"})
    device_has_labels = dr.DeviceEntry(
        labels={"label1", "label2"}, area_id=area_with_labels.id
    )
    device_no_labels = dr.DeviceEntry(
        id="device-no-labels", area_id=area_without_labels.id
    )

    mock_device_registry(
        hass,
        {
            device_has_label1.id: device_has_label1,
            device_has_label2.id: device_has_label2,
            device_has_labels.id: device_has_labels,
            device_no_labels.id: device_no_labels,
        },
    )

    entity_with_my_label = er.RegistryEntry(
        entity_id="light.with_my_label",
        unique_id="with_my_label",
        platform="test",
        labels={"my-label"},
    )
    hidden_entity_with_my_label = er.RegistryEntry(
        entity_id="light.hidden_with_my_label",
        unique_id="hidden_with_my_label",
        platform="test",
        labels={"my-label"},
        hidden_by=er.RegistryEntryHider.USER,
    )
    config_entity_with_my_label = er.RegistryEntry(
        entity_id="light.config_with_my_label",
        unique_id="config_with_my_label",
        platform="test",
        labels={"my-label"},
        entity_category=EntityCategory.CONFIG,
    )
    entity_with_label1_from_device = er.RegistryEntry(
        entity_id="light.with_label1_from_device",
        unique_id="with_label1_from_device",
        platform="test",
        device_id=device_has_label1.id,
    )
    entity_with_label1_and_label2_from_device = er.RegistryEntry(
        entity_id="light.with_label1_and_label2_from_device",
        unique_id="with_label1_and_label2_from_device",
        platform="test",
        labels={"label1"},
        device_id=device_has_label2.id,
    )
    entity_with_labels_from_device = er.RegistryEntry(
        entity_id="light.with_labels_from_device",
        unique_id="with_labels_from_device",
        platform="test",
        device_id=device_has_labels.id,
    )
    entity_with_no_labels = er.RegistryEntry(
        entity_id="light.no_labels",
        unique_id="no_labels",
        platform="test",
        device_id=device_no_labels.id,
    )

    mock_registry(
        hass,
        {
            config_entity_with_my_label.entity_id: config_entity_with_my_label,
            entity_with_label1_and_label2_from_device.entity_id: entity_with_label1_and_label2_from_device,
            entity_with_label1_from_device.entity_id: entity_with_label1_from_device,
            entity_with_labels_from_device.entity_id: entity_with_labels_from_device,
            entity_with_my_label.entity_id: entity_with_my_label,
            entity_with_no_labels.entity_id: entity_with_no_labels,
            hidden_entity_with_my_label.entity_id: hidden_entity_with_my_label,
        },
    )


async def test_call_from_config(hass: HomeAssistant) -> None:
    """Test the sync wrapper of service.async_call_from_config."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    config = {
        "service_template": "{{ 'test_domain.test_service' }}",
        "entity_id": "hello.world",
        "data": {"hello": "goodbye"},
    }

    await hass.async_add_executor_job(service.call_from_config, hass, config)
    await hass.async_block_till_done()

    assert calls[0].data == {"hello": "goodbye", "entity_id": ["hello.world"]}


async def test_service_call(hass: HomeAssistant) -> None:
    """Test service call with templating."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    config = {
        "action": "{{ 'test_domain.test_service' }}",
        "entity_id": "hello.world",
        "data": {
            "hello": "{{ 'goodbye' }}",
            "effect": {"value": "{{ 'complex' }}", "simple": "simple"},
        },
        "data_template": {"list": ["{{ 'list' }}", "2"]},
        "target": {
            "area_id": "test-area-id",
            "entity_id": "will.be_overridden",
            "floor_id": "test-floor-id",
        },
    }

    await service.async_call_from_config(hass, config)
    await hass.async_block_till_done()

    assert dict(calls[0].data) == {
        "hello": "goodbye",
        "effect": {
            "value": "complex",
            "simple": "simple",
        },
        "list": ["list", "2"],
        "entity_id": ["hello.world"],
        "area_id": ["test-area-id"],
        "floor_id": ["test-floor-id"],
    }

    config = {
        "action": "{{ 'test_domain.test_service' }}",
        "target": {
            "area_id": ["area-42", "{{ 'area-51' }}"],
            "device_id": ["abcdef", "{{ 'fedcba' }}"],
            "entity_id": ["light.static", "{{ 'light.dynamic' }}"],
            "floor_id": ["floor-first", "{{ 'floor-second' }}"],
        },
    }

    await service.async_call_from_config(hass, config)
    await hass.async_block_till_done()

    assert dict(calls[1].data) == {
        "area_id": ["area-42", "area-51"],
        "device_id": ["abcdef", "fedcba"],
        "entity_id": ["light.static", "light.dynamic"],
        "floor_id": ["floor-first", "floor-second"],
    }

    config = {
        "action": "{{ 'test_domain.test_service' }}",
        "target": "{{ var_target }}",
    }

    await service.async_call_from_config(
        hass,
        config,
        variables={
            "var_target": {
                "entity_id": "light.static",
                "area_id": ["area-42", "area-51"],
            },
        },
    )
    await hass.async_block_till_done()

    assert dict(calls[2].data) == {
        "area_id": ["area-42", "area-51"],
        "entity_id": ["light.static"],
    }


async def test_service_template_service_call(hass: HomeAssistant) -> None:
    """Test legacy service_template call with templating."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    config = {
        "service_template": "{{ 'test_domain.test_service' }}",
        "entity_id": "hello.world",
        "data": {"hello": "goodbye"},
    }

    await service.async_call_from_config(hass, config)
    await hass.async_block_till_done()

    assert calls[0].data == {"hello": "goodbye", "entity_id": ["hello.world"]}


async def test_passing_variables_to_templates(hass: HomeAssistant) -> None:
    """Test passing variables to templates."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    config = {
        "service_template": "{{ var_service }}",
        "entity_id": "hello.world",
        "data_template": {"hello": "{{ var_data }}"},
    }

    await service.async_call_from_config(
        hass,
        config,
        variables={
            "var_service": "test_domain.test_service",
            "var_data": "goodbye",
        },
    )
    await hass.async_block_till_done()

    assert calls[0].data == {"hello": "goodbye", "entity_id": ["hello.world"]}


async def test_bad_template(hass: HomeAssistant) -> None:
    """Test passing bad template."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    config = {
        "service_template": "{{ var_service }}",
        "entity_id": "hello.world",
        "data_template": {"hello": "{{ states + unknown_var }}"},
    }

    await service.async_call_from_config(
        hass,
        config,
        variables={
            "var_service": "test_domain.test_service",
            "var_data": "goodbye",
        },
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


async def test_split_entity_string(hass: HomeAssistant) -> None:
    """Test splitting of entity string."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    await service.async_call_from_config(
        hass,
        {
            "action": "test_domain.test_service",
            "entity_id": "hello.world, sensor.beer",
        },
    )
    await hass.async_block_till_done()
    assert calls[-1].data.get("entity_id") == ["hello.world", "sensor.beer"]


async def test_not_mutate_input(hass: HomeAssistant) -> None:
    """Test for immutable input."""
    async_mock_service(hass, "test_domain", "test_service")
    config = {
        "action": "test_domain.test_service",
        "entity_id": "hello.world, sensor.beer",
        "data": {"hello": 1},
        "data_template": {"nested": {"value": "{{ 1 + 1 }}"}},
    }
    orig = deepcopy(config)

    # Validate both the original and the copy
    config = cv.SERVICE_SCHEMA(config)
    orig = cv.SERVICE_SCHEMA(orig)

    await service.async_call_from_config(hass, config, validate_config=False)
    assert orig == config


@patch("homeassistant.helpers.service._LOGGER.error")
async def test_fail_silently_if_no_service(mock_log, hass: HomeAssistant) -> None:
    """Test failing if service is missing."""
    await service.async_call_from_config(hass, None)
    assert mock_log.call_count == 1

    await service.async_call_from_config(hass, {})
    assert mock_log.call_count == 2

    await service.async_call_from_config(hass, {"action": "invalid"})
    assert mock_log.call_count == 3


async def test_service_call_entry_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test service call with entity specified by entity registry ID."""
    calls = async_mock_service(hass, "test_domain", "test_service")
    entry = entity_registry.async_get_or_create(
        "hello", "hue", "1234", suggested_object_id="world"
    )

    assert entry.entity_id == "hello.world"

    config = {
        "action": "test_domain.test_service",
        "target": {"entity_id": entry.id},
    }

    await service.async_call_from_config(hass, config)
    await hass.async_block_till_done()

    assert dict(calls[0].data) == {"entity_id": ["hello.world"]}


@pytest.mark.parametrize("target", ["all", "none"])
async def test_service_call_all_none(hass: HomeAssistant, target) -> None:
    """Test service call targeting all."""
    calls = async_mock_service(hass, "test_domain", "test_service")

    config = {
        "action": "test_domain.test_service",
        "target": {"entity_id": target},
    }

    await service.async_call_from_config(hass, config)
    await hass.async_block_till_done()

    assert dict(calls[0].data) == {"entity_id": target}


async def test_extract_entity_ids(hass: HomeAssistant) -> None:
    """Test extract_entity_ids method."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set("light.Kitchen", STATE_OFF)

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await Group.async_create_group(
        hass,
        "test",
        created_by_service=False,
        entity_ids=["light.Ceiling", "light.Kitchen"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    call = ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: "light.Bowl"})

    assert {"light.bowl"} == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: "group.test"})

    assert {"light.ceiling", "light.kitchen"} == await service.async_extract_entity_ids(
        hass, call
    )

    assert {"group.test"} == await service.async_extract_entity_ids(
        hass, call, expand_group=False
    )

    assert (
        await service.async_extract_entity_ids(
            hass,
            ServiceCall("light", "turn_on", {ATTR_ENTITY_ID: ENTITY_MATCH_NONE}),
        )
        == set()
    )


async def test_extract_entity_ids_from_area(
    hass: HomeAssistant, floor_area_mock
) -> None:
    """Test extract_entity_ids method with areas."""
    call = ServiceCall("light", "turn_on", {"area_id": "own-area"})

    assert {
        "light.in_own_area",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"area_id": "test-area"})

    assert {
        "light.in_area",
        "light.assigned_to_area",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"area_id": ["test-area", "diff-area"]})

    assert {
        "light.in_area",
        "light.diff_area",
        "light.assigned_to_area",
    } == await service.async_extract_entity_ids(hass, call)

    assert (
        await service.async_extract_entity_ids(
            hass, ServiceCall("light", "turn_on", {"area_id": ENTITY_MATCH_NONE})
        )
        == set()
    )


async def test_extract_entity_ids_from_devices(
    hass: HomeAssistant, floor_area_mock
) -> None:
    """Test extract_entity_ids method with devices."""
    assert await service.async_extract_entity_ids(
        hass, ServiceCall("light", "turn_on", {"device_id": "device-no-area-id"})
    ) == {
        "light.no_area",
    }

    assert await service.async_extract_entity_ids(
        hass, ServiceCall("light", "turn_on", {"device_id": "device-area-a-id"})
    ) == {
        "light.in_area_a",
        "light.in_area_b",
    }

    assert (
        await service.async_extract_entity_ids(
            hass, ServiceCall("light", "turn_on", {"device_id": "non-existing-id"})
        )
        == set()
    )


@pytest.mark.usefixtures("floor_area_mock")
async def test_extract_entity_ids_from_floor(hass: HomeAssistant) -> None:
    """Test extract_entity_ids method with floors."""
    call = ServiceCall("light", "turn_on", {"floor_id": "test-floor"})

    assert {
        "light.in_area",
        "light.assigned_to_area",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"floor_id": ["test-floor", "floor-a"]})

    assert {
        "light.in_area",
        "light.assigned_to_area",
        "light.in_area_a",
    } == await service.async_extract_entity_ids(hass, call)

    assert (
        await service.async_extract_entity_ids(
            hass, ServiceCall("light", "turn_on", {"floor_id": ENTITY_MATCH_NONE})
        )
        == set()
    )


@pytest.mark.usefixtures("label_mock")
async def test_extract_entity_ids_from_labels(hass: HomeAssistant) -> None:
    """Test extract_entity_ids method with labels."""
    call = ServiceCall("light", "turn_on", {"label_id": "my-label"})

    assert {
        "light.with_my_label",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"label_id": "label1"})

    assert {
        "light.with_label1_from_device",
        "light.with_labels_from_device",
        "light.with_label1_and_label2_from_device",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"label_id": ["label2"]})

    assert {
        "light.with_labels_from_device",
        "light.with_label1_and_label2_from_device",
    } == await service.async_extract_entity_ids(hass, call)

    call = ServiceCall("light", "turn_on", {"label_id": ["label_area"]})

    assert {
        "light.with_labels_from_device",
    } == await service.async_extract_entity_ids(hass, call)

    assert (
        await service.async_extract_entity_ids(
            hass, ServiceCall("light", "turn_on", {"label_id": ENTITY_MATCH_NONE})
        )
        == set()
    )


async def test_async_get_all_descriptions(hass: HomeAssistant) -> None:
    """Test async_get_all_descriptions."""
    group_config = {DOMAIN_GROUP: {}}
    assert await async_setup_component(hass, DOMAIN_GROUP, group_config)
    assert await async_setup_component(hass, DOMAIN_SYSTEM_HEALTH, {})

    with patch(
        "homeassistant.helpers.service._load_services_files",
        side_effect=service._load_services_files,
    ) as proxy_load_services_files:
        descriptions = await service.async_get_all_descriptions(hass)

    # Test we only load services.yaml for integrations with services.yaml
    # And system_health has no services
    assert proxy_load_services_files.mock_calls[0][1][1] == unordered(
        [
            await async_get_integration(hass, DOMAIN_GROUP),
        ]
    )

    assert len(descriptions) == 1
    assert DOMAIN_GROUP in descriptions
    assert "description" in descriptions[DOMAIN_GROUP]["reload"]
    assert "fields" in descriptions[DOMAIN_GROUP]["reload"]

    # Does not have services
    assert DOMAIN_SYSTEM_HEALTH not in descriptions

    logger_config = {DOMAIN_LOGGER: {}}

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        translation_key_prefix = f"component.{DOMAIN_LOGGER}.services.set_default_level"
        return {
            f"{translation_key_prefix}.name": "Translated name",
            f"{translation_key_prefix}.description": "Translated description",
            f"{translation_key_prefix}.fields.level.name": "Field name",
            f"{translation_key_prefix}.fields.level.description": "Field description",
            f"{translation_key_prefix}.fields.level.example": "Field example",
        }

    with patch(
        "homeassistant.helpers.service.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await async_setup_component(hass, DOMAIN_LOGGER, logger_config)
        descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 2
    assert DOMAIN_LOGGER in descriptions
    assert descriptions[DOMAIN_LOGGER]["set_default_level"]["name"] == "Translated name"
    assert (
        descriptions[DOMAIN_LOGGER]["set_default_level"]["description"]
        == "Translated description"
    )
    assert (
        descriptions[DOMAIN_LOGGER]["set_default_level"]["fields"]["level"]["name"]
        == "Field name"
    )
    assert (
        descriptions[DOMAIN_LOGGER]["set_default_level"]["fields"]["level"][
            "description"
        ]
        == "Field description"
    )
    assert (
        descriptions[DOMAIN_LOGGER]["set_default_level"]["fields"]["level"]["example"]
        == "Field example"
    )

    hass.services.async_register(DOMAIN_LOGGER, "new_service", lambda x: None, None)
    service.async_set_service_schema(
        hass, DOMAIN_LOGGER, "new_service", {"description": "new service"}
    )
    descriptions = await service.async_get_all_descriptions(hass)
    assert "description" in descriptions[DOMAIN_LOGGER]["new_service"]
    assert descriptions[DOMAIN_LOGGER]["new_service"]["description"] == "new service"

    hass.services.async_register(
        DOMAIN_LOGGER, "another_new_service", lambda x: None, None
    )
    hass.services.async_register(
        DOMAIN_LOGGER,
        "service_with_optional_response",
        lambda x: None,
        None,
        SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN_LOGGER,
        "service_with_only_response",
        lambda x: None,
        None,
        SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN_LOGGER,
        "another_service_with_response",
        lambda x: None,
        None,
        SupportsResponse.OPTIONAL,
    )
    service.async_set_service_schema(
        hass,
        DOMAIN_LOGGER,
        "another_service_with_response",
        {"description": "response service"},
    )
    descriptions = await service.async_get_all_descriptions(hass)
    assert "another_new_service" in descriptions[DOMAIN_LOGGER]
    assert "service_with_optional_response" in descriptions[DOMAIN_LOGGER]
    assert descriptions[DOMAIN_LOGGER]["service_with_optional_response"][
        "response"
    ] == {"optional": True}
    assert "service_with_only_response" in descriptions[DOMAIN_LOGGER]
    assert descriptions[DOMAIN_LOGGER]["service_with_only_response"]["response"] == {
        "optional": False
    }
    assert "another_service_with_response" in descriptions[DOMAIN_LOGGER]
    assert descriptions[DOMAIN_LOGGER]["another_service_with_response"]["response"] == {
        "optional": True
    }

    # Verify the cache returns the same object
    assert await service.async_get_all_descriptions(hass) is descriptions


async def test_async_get_all_descriptions_dot_keys(hass: HomeAssistant) -> None:
    """Test async_get_all_descriptions with keys starting with a period."""
    service_descriptions = """
        .anchor: &anchor
          selector:
            text:
        test_service:
          fields:
            test: *anchor
    """

    domain = "test_domain"

    hass.services.async_register(domain, "test_service", lambda call: None)
    mock_integration(hass, MockModule(domain), top_level_files={"services.yaml"})
    assert await async_setup_component(hass, domain, {})

    def load_yaml(fname, secrets=None):
        with io.StringIO(service_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "homeassistant.helpers.service._load_services_files",
            side_effect=service._load_services_files,
        ) as proxy_load_services_files,
        patch(
            "homeassistant.util.yaml.loader.load_yaml",
            side_effect=load_yaml,
        ) as mock_load_yaml,
    ):
        descriptions = await service.async_get_all_descriptions(hass)

    mock_load_yaml.assert_called_once_with("services.yaml", None)
    assert proxy_load_services_files.mock_calls[0][1][1] == unordered(
        [
            await async_get_integration(hass, domain),
        ]
    )

    assert descriptions == {
        "test_domain": {
            "test_service": {
                "description": "",
                "fields": {"test": {"selector": {"text": None}}},
                "name": "",
            }
        }
    }


async def test_async_get_all_descriptions_filter(hass: HomeAssistant) -> None:
    """Test async_get_all_descriptions with filters."""
    service_descriptions = """
        test_service:
          target:
            entity:
              domain: alarm_control_panel
              supported_features:
                - alarm_control_panel.AlarmControlPanelEntityFeature.ARM_HOME
          fields:
            temperature:
              filter:
                supported_features:
                  - alarm_control_panel.AlarmControlPanelEntityFeature.ARM_HOME
                attribute:
                  supported_color_modes:
                    - light.ColorMode.COLOR_TEMP
              selector:
                number:
            advanced_stuff:
              fields:
                temperature:
                  filter:
                    supported_features:
                      - alarm_control_panel.AlarmControlPanelEntityFeature.ARM_HOME
                    attribute:
                      supported_color_modes:
                        - light.ColorMode.COLOR_TEMP
                  selector:
                    number:
    """

    domain = "test_domain"

    hass.services.async_register(domain, "test_service", lambda call: None)
    mock_integration(hass, MockModule(domain), top_level_files={"services.yaml"})
    assert await async_setup_component(hass, domain, {})

    def load_yaml(fname, secrets=None):
        with io.StringIO(service_descriptions) as file:
            return parse_yaml(file)

    with (
        patch(
            "homeassistant.helpers.service._load_services_files",
            side_effect=service._load_services_files,
        ) as proxy_load_services_files,
        patch(
            "homeassistant.util.yaml.loader.load_yaml",
            side_effect=load_yaml,
        ) as mock_load_yaml,
    ):
        descriptions = await service.async_get_all_descriptions(hass)

    mock_load_yaml.assert_called_once_with("services.yaml", None)
    assert proxy_load_services_files.mock_calls[0][1][1] == unordered(
        [
            await async_get_integration(hass, domain),
        ]
    )

    test_service_schema = {
        "description": "",
        "fields": {
            "advanced_stuff": {
                "fields": {
                    "temperature": {
                        "filter": {
                            "attribute": {"supported_color_modes": ["color_temp"]},
                            "supported_features": [1],
                        },
                        "selector": {"number": None},
                    },
                },
            },
            "temperature": {
                "filter": {
                    "attribute": {"supported_color_modes": ["color_temp"]},
                    "supported_features": [1],
                },
                "selector": {"number": None},
            },
        },
        "name": "",
        "target": {
            "entity": [
                {
                    "domain": ["alarm_control_panel"],
                    "supported_features": [1],
                },
            ],
        },
    }

    assert descriptions == {
        "test_domain": {"test_service": test_service_schema},
    }


async def test_async_get_all_descriptions_failing_integration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_get_all_descriptions when async_get_integrations returns an exception."""
    group_config = {DOMAIN_GROUP: {}}
    await async_setup_component(hass, DOMAIN_GROUP, group_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert "description" in descriptions["group"]["reload"]
    assert "fields" in descriptions["group"]["reload"]

    logger_config = {DOMAIN_LOGGER: {}}
    await async_setup_component(hass, DOMAIN_LOGGER, logger_config)
    with (
        patch(
            "homeassistant.helpers.service.async_get_integrations",
            return_value={"logger": ImportError},
        ),
        patch(
            "homeassistant.helpers.service.translation.async_get_translations",
            return_value={},
        ),
    ):
        descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 2
    assert "Failed to load integration: logger" in caplog.text

    # Services are empty defaults if the load fails but should
    # not raise
    assert descriptions[DOMAIN_LOGGER]["set_level"] == {
        "description": "",
        "fields": {},
        "name": "",
    }

    hass.services.async_register(DOMAIN_LOGGER, "new_service", lambda x: None, None)
    service.async_set_service_schema(
        hass, DOMAIN_LOGGER, "new_service", {"description": "new service"}
    )
    descriptions = await service.async_get_all_descriptions(hass)
    assert "description" in descriptions[DOMAIN_LOGGER]["new_service"]
    assert descriptions[DOMAIN_LOGGER]["new_service"]["description"] == "new service"

    hass.services.async_register(
        DOMAIN_LOGGER, "another_new_service", lambda x: None, None
    )
    hass.services.async_register(
        DOMAIN_LOGGER,
        "service_with_optional_response",
        lambda x: None,
        None,
        SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN_LOGGER,
        "service_with_only_response",
        lambda x: None,
        None,
        SupportsResponse.ONLY,
    )

    descriptions = await service.async_get_all_descriptions(hass)
    assert "another_new_service" in descriptions[DOMAIN_LOGGER]
    assert "service_with_optional_response" in descriptions[DOMAIN_LOGGER]
    assert descriptions[DOMAIN_LOGGER]["service_with_optional_response"][
        "response"
    ] == {"optional": True}
    assert "service_with_only_response" in descriptions[DOMAIN_LOGGER]
    assert descriptions[DOMAIN_LOGGER]["service_with_only_response"]["response"] == {
        "optional": False
    }

    # Verify the cache returns the same object
    assert await service.async_get_all_descriptions(hass) is descriptions


async def test_async_get_all_descriptions_dynamically_created_services(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_get_all_descriptions when async_get_integrations when services are dynamic."""
    group_config = {DOMAIN_GROUP: {}}
    await async_setup_component(hass, DOMAIN_GROUP, group_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert "description" in descriptions["group"]["reload"]
    assert "fields" in descriptions["group"]["reload"]

    shell_command_config = {DOMAIN_SHELL_COMMAND: {"test_service": "ls /bin"}}
    await async_setup_component(hass, DOMAIN_SHELL_COMMAND, shell_command_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 2
    assert descriptions[DOMAIN_SHELL_COMMAND]["test_service"] == {
        "description": "",
        "fields": {},
        "name": "",
        "response": {"optional": True},
    }


async def test_async_get_all_descriptions_new_service_added_while_loading(
    hass: HomeAssistant,
) -> None:
    """Test async_get_all_descriptions when a new service is added while loading translations."""
    group_config = {DOMAIN_GROUP: {}}
    await async_setup_component(hass, DOMAIN_GROUP, group_config)
    descriptions = await service.async_get_all_descriptions(hass)

    assert len(descriptions) == 1

    assert "description" in descriptions["group"]["reload"]
    assert "fields" in descriptions["group"]["reload"]

    logger_domain = DOMAIN_LOGGER
    logger_config = {logger_domain: {}}

    translations_called = asyncio.Event()
    translations_wait = asyncio.Event()

    async def async_get_translations(
        hass: HomeAssistant,
        language: str,
        category: str,
        integrations: Iterable[str] | None = None,
        config_flow: bool | None = None,
    ) -> dict[str, Any]:
        """Return all backend translations."""
        translations_called.set()
        await translations_wait.wait()
        translation_key_prefix = f"component.{logger_domain}.services.set_default_level"
        return {
            f"{translation_key_prefix}.name": "Translated name",
            f"{translation_key_prefix}.description": "Translated description",
            f"{translation_key_prefix}.fields.level.name": "Field name",
            f"{translation_key_prefix}.fields.level.description": "Field description",
            f"{translation_key_prefix}.fields.level.example": "Field example",
        }

    with patch(
        "homeassistant.helpers.service.translation.async_get_translations",
        side_effect=async_get_translations,
    ):
        await async_setup_component(hass, logger_domain, logger_config)
        task = asyncio.create_task(service.async_get_all_descriptions(hass))
        await translations_called.wait()
        # Now register a new service while translations are being loaded
        hass.services.async_register(logger_domain, "new_service", lambda x: None, None)
        service.async_set_service_schema(
            hass, logger_domain, "new_service", {"description": "new service"}
        )
        translations_wait.set()
        descriptions = await task

    # Two domains should be present
    assert len(descriptions) == 2

    logger_descriptions = descriptions[logger_domain]

    # The new service was loaded after the translations were loaded
    # so it should not appear until the next time we fetch
    assert "new_service" not in logger_descriptions

    set_default_level = logger_descriptions["set_default_level"]

    assert set_default_level["name"] == "Translated name"
    assert set_default_level["description"] == "Translated description"
    set_default_level_fields = set_default_level["fields"]
    assert set_default_level_fields["level"]["name"] == "Field name"
    assert set_default_level_fields["level"]["description"] == "Field description"
    assert set_default_level_fields["level"]["example"] == "Field example"

    descriptions = await service.async_get_all_descriptions(hass)
    assert "description" in descriptions[logger_domain]["new_service"]
    assert descriptions[logger_domain]["new_service"]["description"] == "new service"


async def test_register_with_mixed_case(hass: HomeAssistant) -> None:
    """Test registering a service with mixed case.

    For backwards compatibility, we have historically allowed mixed case,
    and automatically converted it to lowercase.
    """
    logger_config = {DOMAIN_LOGGER: {}}
    await async_setup_component(hass, DOMAIN_LOGGER, logger_config)
    logger_domain_mixed = "LoGgEr"
    hass.services.async_register(
        logger_domain_mixed, "NeW_SeRVICE", lambda x: None, None
    )
    service.async_set_service_schema(
        hass, logger_domain_mixed, "NeW_SeRVICE", {"description": "new service"}
    )
    descriptions = await service.async_get_all_descriptions(hass)
    assert "description" in descriptions[DOMAIN_LOGGER]["new_service"]
    assert descriptions[DOMAIN_LOGGER]["new_service"]["description"] == "new service"


async def test_call_with_required_features(hass: HomeAssistant, mock_entities) -> None:
    """Test service calls invoked only if entity has required features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        mock_entities,
        HassJob(test_service_mock),
        ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A],
    )

    assert test_service_mock.call_count == 2
    expected = [
        mock_entities["light.kitchen"],
        mock_entities["light.bedroom"],
    ]
    actual = [call[0][0] for call in test_service_mock.call_args_list]
    assert all(entity in actual for entity in expected)

    # Test we raise if we target entity ID that does not support the service
    test_service_mock.reset_mock()
    with pytest.raises(exceptions.HomeAssistantError):
        await service.entity_service_call(
            hass,
            mock_entities,
            HassJob(test_service_mock),
            ServiceCall(
                "test_domain", "test_service", {"entity_id": "light.living_room"}
            ),
            required_features=[SUPPORT_A],
        )
    assert test_service_mock.call_count == 0


async def test_call_with_both_required_features(
    hass: HomeAssistant, mock_entities
) -> None:
    """Test service calls invoked only if entity has both features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        mock_entities,
        HassJob(test_service_mock),
        ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A | SUPPORT_B],
    )

    assert test_service_mock.call_count == 1
    assert [call[0][0] for call in test_service_mock.call_args_list] == [
        mock_entities["light.bedroom"]
    ]


async def test_call_with_one_of_required_features(
    hass: HomeAssistant, mock_entities
) -> None:
    """Test service calls invoked with one entity having the required features."""
    test_service_mock = AsyncMock(return_value=None)
    await service.entity_service_call(
        hass,
        mock_entities,
        HassJob(test_service_mock),
        ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
        required_features=[SUPPORT_A, SUPPORT_C],
    )

    assert test_service_mock.call_count == 3
    expected = [
        mock_entities["light.kitchen"],
        mock_entities["light.bedroom"],
        mock_entities["light.bathroom"],
    ]
    actual = [call[0][0] for call in test_service_mock.call_args_list]
    assert all(entity in actual for entity in expected)


async def test_call_with_sync_func(hass: HomeAssistant, mock_entities) -> None:
    """Test invoking sync service calls."""
    test_service_mock = Mock(return_value=None)
    await service.entity_service_call(
        hass,
        mock_entities,
        HassJob(test_service_mock),
        ServiceCall("test_domain", "test_service", {"entity_id": "light.kitchen"}),
    )
    assert test_service_mock.call_count == 1


async def test_call_with_sync_attr(hass: HomeAssistant, mock_entities) -> None:
    """Test invoking sync service calls."""
    mock_method = mock_entities["light.kitchen"].sync_method = Mock(return_value=None)
    await service.entity_service_call(
        hass,
        mock_entities,
        "sync_method",
        ServiceCall(
            "test_domain",
            "test_service",
            {"entity_id": "light.kitchen", "area_id": "abcd"},
        ),
    )
    assert mock_method.call_count == 1
    # We pass empty kwargs because both entity_id and area_id are filtered out
    assert mock_method.mock_calls[0][2] == {}


async def test_call_context_user_not_exist(hass: HomeAssistant) -> None:
    """Check we don't allow deleted users to do things."""
    with pytest.raises(exceptions.UnknownUser) as err:
        await service.entity_service_call(
            hass,
            {},
            Mock(),
            ServiceCall(
                "test_domain",
                "test_service",
                context=Context(user_id="non-existing"),
            ),
        )

    assert err.value.context.user_id == "non-existing"


async def test_call_context_target_all(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check we only target allowed entities if targeting all."""
    with patch(
        "homeassistant.auth.AuthManager.async_get_user",
        return_value=Mock(
            permissions=PolicyPermissions(
                {"entities": {"entity_ids": {"light.kitchen": True}}}, None
            ),
            is_admin=False,
        ),
    ):
        await service.entity_service_call(
            hass,
            mock_entities,
            Mock(),
            ServiceCall(
                "test_domain",
                "test_service",
                data={"entity_id": ENTITY_MATCH_ALL},
                context=Context(user_id="mock-id"),
            ),
        )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_context_target_specific(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check targeting specific entities."""
    with patch(
        "homeassistant.auth.AuthManager.async_get_user",
        return_value=Mock(
            permissions=PolicyPermissions(
                {"entities": {"entity_ids": {"light.kitchen": True}}}, None
            )
        ),
    ):
        await service.entity_service_call(
            hass,
            mock_entities,
            Mock(),
            ServiceCall(
                "test_domain",
                "test_service",
                {"entity_id": "light.kitchen"},
                context=Context(user_id="mock-id"),
            ),
        )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_context_target_specific_no_auth(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check targeting specific entities without auth."""
    with (
        pytest.raises(exceptions.Unauthorized) as err,
        patch(
            "homeassistant.auth.AuthManager.async_get_user",
            return_value=Mock(permissions=PolicyPermissions({}, None), is_admin=False),
        ),
    ):
        await service.entity_service_call(
            hass,
            mock_entities,
            Mock(),
            ServiceCall(
                "test_domain",
                "test_service",
                {"entity_id": "light.kitchen"},
                context=Context(user_id="mock-id"),
            ),
        )

    assert err.value.context.user_id == "mock-id"
    assert err.value.entity_id == "light.kitchen"


async def test_call_no_context_target_all(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check we target all if no user context given."""
    await service.entity_service_call(
        hass,
        mock_entities,
        Mock(),
        ServiceCall(
            "test_domain", "test_service", data={"entity_id": ENTITY_MATCH_ALL}
        ),
    )

    assert len(mock_handle_entity_call.mock_calls) == 4
    assert [call[1][1] for call in mock_handle_entity_call.mock_calls] == list(
        mock_entities.values()
    )


async def test_call_no_context_target_specific(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check we can target specified entities."""
    await service.entity_service_call(
        hass,
        mock_entities,
        Mock(),
        ServiceCall(
            "test_domain",
            "test_service",
            {"entity_id": ["light.kitchen", "light.non-existing"]},
        ),
    )

    assert len(mock_handle_entity_call.mock_calls) == 1
    assert mock_handle_entity_call.mock_calls[0][1][1].entity_id == "light.kitchen"


async def test_call_with_match_all(
    hass: HomeAssistant,
    mock_handle_entity_call,
    mock_entities,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Check we only target allowed entities if targeting all."""
    await service.entity_service_call(
        hass,
        mock_entities,
        Mock(),
        ServiceCall("test_domain", "test_service", {"entity_id": "all"}),
    )

    assert len(mock_handle_entity_call.mock_calls) == 4
    assert [call[1][1] for call in mock_handle_entity_call.mock_calls] == list(
        mock_entities.values()
    )


async def test_call_with_omit_entity_id(
    hass: HomeAssistant, mock_handle_entity_call, mock_entities
) -> None:
    """Check service call if we do not pass an entity ID."""
    await service.entity_service_call(
        hass,
        mock_entities,
        Mock(),
        ServiceCall("test_domain", "test_service"),
    )

    assert len(mock_handle_entity_call.mock_calls) == 0


async def test_register_admin_service(
    hass: HomeAssistant, hass_read_only_user: MockUser, hass_admin_user: MockUser
) -> None:
    """Test the register admin service."""
    calls = []

    async def mock_service(call):
        calls.append(call)

    service.async_register_admin_service(hass, "test", "test", mock_service)
    service.async_register_admin_service(
        hass,
        "test",
        "test2",
        mock_service,
        vol.Schema({vol.Required("required"): cv.boolean}),
    )

    with pytest.raises(exceptions.UnknownUser):
        await hass.services.async_call(
            "test",
            "test",
            {},
            blocking=True,
            context=Context(user_id="non-existing"),
        )
    assert len(calls) == 0

    with pytest.raises(exceptions.Unauthorized):
        await hass.services.async_call(
            "test",
            "test",
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )
    assert len(calls) == 0

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "test",
            "test",
            {"invalid": True},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
    assert len(calls) == 0

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "test",
            "test2",
            {},
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
    assert len(calls) == 0

    await hass.services.async_call(
        "test",
        "test2",
        {"required": True},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    assert len(calls) == 1
    assert calls[0].context.user_id == hass_admin_user.id


async def test_domain_control_not_async(hass: HomeAssistant, mock_entities) -> None:
    """Test domain verification in a service call with an unknown user."""
    calls = []

    def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    with pytest.raises(exceptions.HomeAssistantError):
        service.verify_domain_control(hass, "test_domain")(mock_service_log)


async def test_domain_control_unknown(hass: HomeAssistant, mock_entities) -> None:
    """Test domain verification in a service call with an unknown user."""
    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    with patch(
        "homeassistant.helpers.entity_registry.async_get",
        return_value=Mock(entities=mock_entities),
    ):
        protected_mock_service = service.verify_domain_control(hass, "test_domain")(
            mock_service_log
        )

        hass.services.async_register(
            "test_domain", "test_service", protected_mock_service, schema=None
        )

        with pytest.raises(exceptions.UnknownUser):
            await hass.services.async_call(
                "test_domain",
                "test_service",
                {},
                blocking=True,
                context=Context(user_id="fake_user_id"),
            )
        assert len(calls) == 0


async def test_domain_control_unauthorized(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test domain verification in a service call with an unauthorized user."""
    mock_registry(
        hass,
        {
            "light.kitchen": er.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = service.verify_domain_control(hass, "test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    with pytest.raises(exceptions.Unauthorized):
        await hass.services.async_call(
            "test_domain",
            "test_service",
            {},
            blocking=True,
            context=Context(user_id=hass_read_only_user.id),
        )

    assert len(calls) == 0


async def test_domain_control_admin(
    hass: HomeAssistant, hass_admin_user: MockUser
) -> None:
    """Test domain verification in a service call with an admin user."""
    mock_registry(
        hass,
        {
            "light.kitchen": er.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = service.verify_domain_control(hass, "test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    await hass.services.async_call(
        "test_domain",
        "test_service",
        {},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )

    assert len(calls) == 1


async def test_domain_control_no_user(hass: HomeAssistant) -> None:
    """Test domain verification in a service call with no user."""
    mock_registry(
        hass,
        {
            "light.kitchen": er.RegistryEntry(
                entity_id="light.kitchen",
                unique_id="kitchen",
                platform="test_domain",
            )
        },
    )

    calls = []

    async def mock_service_log(call):
        """Define a protected service."""
        calls.append(call)

    protected_mock_service = service.verify_domain_control(hass, "test_domain")(
        mock_service_log
    )

    hass.services.async_register(
        "test_domain", "test_service", protected_mock_service, schema=None
    )

    await hass.services.async_call(
        "test_domain",
        "test_service",
        {},
        blocking=True,
        context=Context(user_id=None),
    )

    assert len(calls) == 1


async def test_extract_from_service_available_device(hass: HomeAssistant) -> None:
    """Test the extraction of entity from service and device is available."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2", available=False),
        MockEntity(name="test_3", entity_id="test_domain.test_3"),
        MockEntity(name="test_4", entity_id="test_domain.test_4", available=False),
    ]

    call_1 = ServiceCall("test", "service", data={"entity_id": ENTITY_MATCH_ALL})

    assert [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call_1))
    ] == ["test_domain.test_1", "test_domain.test_3"]

    call_2 = ServiceCall(
        "test",
        "service",
        data={"entity_id": ["test_domain.test_3", "test_domain.test_4"]},
    )

    assert [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call_2))
    ] == ["test_domain.test_3"]

    assert (
        await service.async_extract_entities(
            hass,
            entities,
            ServiceCall(
                "test",
                "service",
                data={"entity_id": ENTITY_MATCH_NONE},
            ),
        )
        == []
    )


async def test_extract_from_service_empty_if_no_entity_id(hass: HomeAssistant) -> None:
    """Test the extraction from service without specifying entity."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2"),
    ]
    call = ServiceCall("test", "service")

    assert [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call))
    ] == []


async def test_extract_from_service_filter_out_non_existing_entities(
    hass: HomeAssistant,
) -> None:
    """Test the extraction of non existing entities from service."""
    entities = [
        MockEntity(name="test_1", entity_id="test_domain.test_1"),
        MockEntity(name="test_2", entity_id="test_domain.test_2"),
    ]

    call = ServiceCall(
        "test",
        "service",
        {"entity_id": ["test_domain.test_2", "test_domain.non_exist"]},
    )

    assert [
        ent.entity_id
        for ent in (await service.async_extract_entities(hass, entities, call))
    ] == ["test_domain.test_2"]


async def test_extract_from_service_area_id(
    hass: HomeAssistant, floor_area_mock
) -> None:
    """Test the extraction using area ID as reference."""
    entities = [
        MockEntity(name="in_area", entity_id="light.in_area"),
        MockEntity(name="no_area", entity_id="light.no_area"),
        MockEntity(name="diff_area", entity_id="light.diff_area"),
    ]

    call = ServiceCall("light", "turn_on", {"area_id": "test-area"})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 1
    assert extracted[0].entity_id == "light.in_area"

    call = ServiceCall("light", "turn_on", {"area_id": ["test-area", "diff-area"]})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 2
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.diff_area",
        "light.in_area",
    ]

    call = ServiceCall(
        "light",
        "turn_on",
        {"area_id": ["test-area", "diff-area"], "device_id": "device-no-area-id"},
    )
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 3
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.diff_area",
        "light.in_area",
        "light.no_area",
    ]


@pytest.mark.usefixtures("label_mock")
async def test_extract_from_service_label_id(hass: HomeAssistant) -> None:
    """Test the extraction using label ID as reference."""
    entities = [
        MockEntity(name="with_my_label", entity_id="light.with_my_label"),
        MockEntity(name="no_labels", entity_id="light.no_labels"),
        MockEntity(
            name="with_labels_from_device", entity_id="light.with_labels_from_device"
        ),
    ]

    call = ServiceCall("light", "turn_on", {"label_id": "label_area"})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 1
    assert extracted[0].entity_id == "light.with_labels_from_device"

    call = ServiceCall("light", "turn_on", {"label_id": "my-label"})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 1
    assert extracted[0].entity_id == "light.with_my_label"

    call = ServiceCall("light", "turn_on", {"label_id": ["my-label", "label1"]})
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 2
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.with_labels_from_device",
        "light.with_my_label",
    ]

    call = ServiceCall(
        "light",
        "turn_on",
        {"label_id": ["my-label", "label1"], "device_id": "device-no-labels"},
    )
    extracted = await service.async_extract_entities(hass, entities, call)
    assert len(extracted) == 3
    assert sorted(ent.entity_id for ent in extracted) == [
        "light.no_labels",
        "light.with_labels_from_device",
        "light.with_my_label",
    ]


async def test_entity_service_call_warn_referenced(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we only warn for referenced entities in entity_service_call."""
    call = ServiceCall(
        "light",
        "turn_on",
        {
            "area_id": "non-existent-area",
            "entity_id": "non.existent",
            "device_id": "non-existent-device",
            "floor_id": "non-existent-floor",
            "label_id": "non-existent-label",
        },
    )
    await service.entity_service_call(hass, {}, "", call)
    assert (
        "Referenced floors non-existent-floor, areas non-existent-area, "
        "devices non-existent-device, entities non.existent, "
        "labels non-existent-label are missing or not currently available"
    ) in caplog.text


async def test_async_extract_entities_warn_referenced(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test we only warn for referenced entities in async_extract_entities."""
    call = ServiceCall(
        "light",
        "turn_on",
        {
            "area_id": "non-existent-area",
            "entity_id": "non.existent",
            "device_id": "non-existent-device",
            "floor_id": "non-existent-floor",
            "label_id": "non-existent-label",
        },
    )
    extracted = await service.async_extract_entities(hass, {}, call)
    assert len(extracted) == 0
    assert (
        "Referenced floors non-existent-floor, areas non-existent-area, "
        "devices non-existent-device, entities non.existent, "
        "labels non-existent-label are missing or not currently available"
    ) in caplog.text


async def test_async_extract_config_entry_ids(hass: HomeAssistant) -> None:
    """Test we can find devices that have no entities."""

    device_no_entities = dr.DeviceEntry(id="device-no-entities", config_entries={"abc"})

    call = ServiceCall(
        "homeassistant",
        "reload_config_entry",
        {
            "device_id": "device-no-entities",
        },
    )

    mock_device_registry(
        hass,
        {
            device_no_entities.id: device_no_entities,
        },
    )

    assert await service.async_extract_config_entry_ids(hass, call) == {"abc"}


async def test_reload_service_helper(hass: HomeAssistant) -> None:
    """Test the reload service helper."""

    active_reload_calls = 0
    reloaded = []

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Remove all automations and load new ones from config."""
        nonlocal active_reload_calls
        # Assert the reload helper prevents parallel reloads
        assert not active_reload_calls
        active_reload_calls += 1
        if not (target := service_call.data.get("target")):
            reloaded.append("all")
        else:
            reloaded.append(target)
        await asyncio.sleep(0.01)
        active_reload_calls -= 1

    def reload_targets(service_call: ServiceCall) -> set[str | None]:
        if target_id := service_call.data.get("target"):
            return {target_id}
        return {"target1", "target2", "target3", "target4"}

    # Test redundant reload of single targets
    reloader = service.ReloadServiceHelper(reload_service_handler, reload_targets)
    tasks = [
        # This reload task will start executing first, (target1)
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        # These reload tasks will be deduplicated to (target2, target3, target4, target1)
        # while the first task is reloaded, note that target1 can't be deduplicated
        # because it's already being reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(
        ["target1", "target2", "target3", "target4", "target1"]
    )

    # Test redundant reload of multiple targets + single target
    reloaded.clear()
    tasks = [
        # This reload task will start executing first, (target1)
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        # These reload tasks will be deduplicated to (target2, target3, target4, all)
        # while the first task is reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test")),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(["target1", "target2", "target3", "target4", "all"])

    # Test redundant reload of multiple targets + single target
    reloaded.clear()
    tasks = [
        # This reload task will start executing first, (all)
        reloader.execute_service(ServiceCall("test", "test")),
        # These reload tasks will be deduplicated to (target1, target2, target3, target4)
        # while the first task is reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(["all", "target1", "target2", "target3", "target4"])

    # Test redundant reload of single targets
    reloaded.clear()
    tasks = [
        # This reload task will start executing first, (target1)
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        # These reload tasks will be deduplicated to (target2, target3, target4, target1)
        # while the first task is reloaded, note that target1 can't be deduplicated
        # because it's already being reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(
        ["target1", "target2", "target3", "target4", "target1"]
    )

    # Test redundant reload of multiple targets + single target
    reloaded.clear()
    tasks = [
        # This reload task will start executing first, (target1)
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        # These reload tasks will be deduplicated to (target2, target3, target4, all)
        # while the first task is reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test")),
        reloader.execute_service(ServiceCall("test", "test")),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(["target1", "target2", "target3", "target4", "all"])

    # Test redundant reload of multiple targets + single target
    reloaded.clear()
    tasks = [
        # This reload task will start executing first, (all)
        reloader.execute_service(ServiceCall("test", "test")),
        # These reload tasks will be deduplicated to (target1, target2, target3, target4)
        # while the first task is reloaded.
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target1"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target2"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target3"})),
        reloader.execute_service(ServiceCall("test", "test", {"target": "target4"})),
    ]
    await asyncio.gather(*tasks)
    assert reloaded == unordered(["all", "target1", "target2", "target3", "target4"])
