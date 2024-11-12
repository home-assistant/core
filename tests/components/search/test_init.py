"""Tests for Search integration."""

import pytest
from pytest_unordered import unordered

from homeassistant.components.search import ItemType, Searcher
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.helpers.entity import EntityInfo
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


async def test_search(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    floor_registry: fr.FloorRegistry,
    label_registry: lr.LabelRegistry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test search."""
    assert await async_setup_component(hass, "search", {})

    # Labels
    label_energy = label_registry.async_create("Energy")
    label_christmas = label_registry.async_create("Christmas")
    label_other = label_registry.async_create("Other")

    # Floors
    first_floor = floor_registry.async_create("First Floor")
    second_floor = floor_registry.async_create("Second Floor")

    # Areas
    bedroom_area = area_registry.async_create(
        "Bedroom", floor_id=second_floor.floor_id, labels={label_other.label_id}
    )
    kitchen_area = area_registry.async_create("Kitchen", floor_id=first_floor.floor_id)
    living_room_area = area_registry.async_create(
        "Living Room", floor_id=first_floor.floor_id
    )

    # Config entries
    hue_config_entry = MockConfigEntry(domain="hue")
    hue_config_entry.add_to_hass(hass)
    wled_config_entry = MockConfigEntry(domain="wled")
    wled_config_entry.add_to_hass(hass)

    # Devices
    hue_device = device_registry.async_get_or_create(
        config_entry_id=hue_config_entry.entry_id,
        name="Light Strip",
        identifiers={("hue", "hue-1")},
    )
    device_registry.async_update_device(hue_device.id, area_id=kitchen_area.id)

    wled_device = device_registry.async_get_or_create(
        config_entry_id=wled_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"wled", "wled-1"}),
    )
    device_registry.async_update_device(
        wled_device.id, area_id=living_room_area.id, labels={label_christmas.label_id}
    )

    # Entities
    hue_segment_1_entity = entity_registry.async_get_or_create(
        "light",
        "hue",
        "hue-1-seg-1",
        suggested_object_id="hue segment 1",
        config_entry=hue_config_entry,
        device_id=hue_device.id,
    )
    entity_registry.async_update_entity(
        hue_segment_1_entity.entity_id, labels={label_energy.label_id}
    )
    hue_segment_2_entity = entity_registry.async_get_or_create(
        "light",
        "hue",
        "hue-1-seg-2",
        suggested_object_id="hue segment 2",
        config_entry=hue_config_entry,
        device_id=hue_device.id,
    )
    wled_segment_1_entity = entity_registry.async_get_or_create(
        "light",
        "wled",
        "wled-1-seg-1",
        suggested_object_id="wled segment 1",
        config_entry=wled_config_entry,
        device_id=wled_device.id,
    )
    wled_segment_2_entity = entity_registry.async_get_or_create(
        "light",
        "wled",
        "wled-1-seg-2",
        suggested_object_id="wled segment 2",
        config_entry=wled_config_entry,
        device_id=wled_device.id,
    )
    entity_registry.async_update_entity(
        wled_segment_2_entity.entity_id, area_id=bedroom_area.id
    )

    scene_wled_hue_entity = entity_registry.async_get_or_create(
        "scene",
        "homeassistant",
        "wled_hue",
        suggested_object_id="scene_wled_hue",
    )
    entity_registry.async_update_entity(
        scene_wled_hue_entity.entity_id,
        area_id=bedroom_area.id,
        labels={label_other.label_id},
    )

    # Persons can technically be assigned to areas
    person_paulus_entity = entity_registry.async_get_or_create(
        "person",
        "person",
        "abcd",
        suggested_object_id="paulus",
    )
    entity_registry.async_update_entity(
        person_paulus_entity.entity_id,
        area_id=bedroom_area.id,
        labels={label_other.label_id},
    )

    script_scene_entity = entity_registry.async_get_or_create(
        "script",
        "script",
        "scene",
        suggested_object_id="scene",
    )
    entity_registry.async_update_entity(
        script_scene_entity.entity_id,
        area_id=bedroom_area.id,
        labels={label_other.label_id},
    )

    # Entity sources
    entity_sources = {
        "light.wled_platform_config_source": EntityInfo(
            domain="wled",
        ),
        "light.wled_config_entry_source": EntityInfo(
            config_entry=wled_config_entry.entry_id,
            domain="wled",
        ),
    }

    # Groups
    await async_setup_component(
        hass,
        "group",
        {
            "group": {
                "wled": {
                    "name": "wled",
                    "entities": [
                        wled_segment_1_entity.entity_id,
                        wled_segment_2_entity.entity_id,
                    ],
                },
                "hue": {
                    "name": "hue",
                    "entities": [
                        hue_segment_1_entity.entity_id,
                        hue_segment_2_entity.entity_id,
                    ],
                },
                "wled_hue": {
                    "name": "wled and hue",
                    "entities": [
                        wled_segment_1_entity.entity_id,
                        wled_segment_2_entity.entity_id,
                        hue_segment_1_entity.entity_id,
                        hue_segment_2_entity.entity_id,
                    ],
                },
            }
        },
    )

    # Persons
    assert await async_setup_component(
        hass,
        "person",
        {
            "person": [
                {
                    "id": "abcd",
                    "name": "Paulus",
                    "device_trackers": ["device_tracker.paulus_iphone"],
                }
            ]
        },
    )

    # Scenes
    await async_setup_component(
        hass,
        "scene",
        {
            "scene": [
                {
                    "name": "scene_wled_seg_1",
                    "entities": {wled_segment_1_entity.entity_id: "on"},
                },
                {
                    "name": "scene_hue_seg_1",
                    "entities": {hue_segment_1_entity.entity_id: "on"},
                },
                {
                    "id": "wled_hue",
                    "name": "scene_wled_hue",
                    "entities": {
                        wled_segment_1_entity.entity_id: "on",
                        wled_segment_2_entity.entity_id: "on",
                        hue_segment_1_entity.entity_id: "on",
                        hue_segment_2_entity.entity_id: "on",
                    },
                },
            ]
        },
    )

    # Automations
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "id": "unique_id",
                    "alias": "blueprint_automation_1",
                    "triggers": {"platform": "template", "value_template": "true"},
                    "use_blueprint": {
                        "path": "test_event_service.yaml",
                        "input": {
                            "trigger_event": "blueprint_event_1",
                            "service_to_call": "test.automation_1",
                            "a_number": 5,
                        },
                    },
                },
                {
                    "alias": "blueprint_automation_2",
                    "triggers": {"platform": "template", "value_template": "true"},
                    "use_blueprint": {
                        "path": "test_event_service.yaml",
                        "input": {
                            "trigger_event": "blueprint_event_2",
                            "service_to_call": "test.automation_2",
                            "a_number": 5,
                        },
                    },
                },
                {
                    "alias": "wled_entity",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": wled_segment_1_entity.entity_id},
                        },
                    ],
                },
                {
                    "alias": "wled_device",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "domain": "light",
                            "device_id": wled_device.id,
                            "entity_id": wled_segment_1_entity.entity_id,
                            "type": "turn_on",
                        },
                    ],
                },
                {
                    "alias": "floor",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "test.script",
                            "target": {"floor_id": first_floor.floor_id},
                        },
                    ],
                },
                {
                    "alias": "area",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "test.script",
                            "target": {"area_id": kitchen_area.id},
                        },
                    ],
                },
                {
                    "alias": "group",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "homeassistant.turn_on",
                            "target": {"entity_id": "group.wled_hue"},
                        },
                    ],
                },
                {
                    "alias": "scene",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "scene": scene_wled_hue_entity.entity_id,
                        },
                    ],
                },
                {
                    "alias": "script",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "script.turn_on",
                            "data": {"entity_id": script_scene_entity.entity_id},
                        },
                    ],
                },
                {
                    "alias": "label",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "script.turn_on",
                            "target": {"label_id": label_christmas.label_id},
                        },
                    ],
                },
            ]
        },
    )

    # Scripts
    assert await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "blueprint_script_1": {
                    "use_blueprint": {
                        "path": "test_service.yaml",
                        "input": {
                            "service_to_call": "test.automation",
                        },
                    }
                },
                "blueprint_script_2": {
                    "use_blueprint": {
                        "path": "test_service.yaml",
                        "input": {
                            "service_to_call": "test.automation",
                        },
                    }
                },
                "wled": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": wled_segment_1_entity.entity_id},
                        },
                    ]
                },
                "hue": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "data": {"entity_id": hue_segment_1_entity.entity_id},
                        },
                    ]
                },
                "script_with_templated_services": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": "{{ {'entity_id':'test.test1'} }}",
                        },
                        {
                            "service": "test.script",
                            "data": "{{ {'entity_id':'test.test2'} }}",
                        },
                        {
                            "service": "test.script",
                            "data_template": "{{ {'entity_id':'test.test3'} }}",
                        },
                    ]
                },
                "device": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": {"device_id": hue_device.id},
                        },
                    ],
                },
                "floor": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": {"floor_id": first_floor.floor_id},
                        },
                    ],
                },
                "area": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": {"area_id": kitchen_area.id},
                        },
                    ],
                },
                "group": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": {"entity_id": "group.wled_hue"},
                        },
                    ],
                },
                "scene": {
                    "sequence": [
                        {
                            "scene": scene_wled_hue_entity.entity_id,
                        },
                    ],
                },
                "label": {
                    "sequence": [
                        {
                            "service": "test.script",
                            "target": {"label_id": label_other.label_id},
                        },
                    ],
                },
                "nested": {
                    "sequence": [
                        {
                            "service": "script.turn_on",
                            "data": {"entity_id": script_scene_entity.entity_id},
                        },
                    ],
                },
            }
        },
    )

    def search(item_type: ItemType, item_id: str) -> dict[str, set[str]]:
        """Search."""
        searcher = Searcher(hass, entity_sources)
        return searcher.async_search(item_type, item_id)

    #
    # Tests
    #
    assert not search(ItemType.AREA, "unknown")
    assert search(ItemType.AREA, bedroom_area.id) == {
        ItemType.AUTOMATION: {"automation.scene", "automation.script"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.ENTITY: {
            wled_segment_2_entity.entity_id,
            scene_wled_hue_entity.entity_id,
            script_scene_entity.entity_id,
            person_paulus_entity.entity_id,
        },
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.LABEL: {label_other.label_id},
        ItemType.PERSON: {person_paulus_entity.entity_id},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id, "script.nested"},
    }
    assert search(ItemType.AREA, living_room_area.id) == {
        ItemType.AUTOMATION: {"automation.wled_device", "automation.wled_entity"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {wled_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.SCENE: {"scene.scene_wled_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.wled"},
    }
    assert search(ItemType.AREA, kitchen_area.id) == {
        ItemType.AUTOMATION: {"automation.area"},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.ENTITY: {
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.hue", "group.wled_hue"},
        ItemType.SCENE: {"scene.scene_hue_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.area", "script.device", "script.hue"},
    }

    assert not search(ItemType.AUTOMATION, "automation.unknown")
    assert search(ItemType.AUTOMATION, "automation.blueprint_automation_1") == {
        ItemType.AUTOMATION_BLUEPRINT: {"test_event_service.yaml"},
        ItemType.ENTITY: {"light.kitchen"},
    }
    assert search(ItemType.AUTOMATION, "automation.blueprint_automation_2") == {
        ItemType.AUTOMATION_BLUEPRINT: {"test_event_service.yaml"},
        ItemType.ENTITY: {"light.kitchen"},
    }
    assert search(ItemType.AUTOMATION, "automation.wled_entity") == {
        ItemType.AREA: {living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {wled_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"wled"},
    }
    assert search(ItemType.AUTOMATION, "automation.wled_device") == {
        ItemType.AREA: {living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"wled"},
    }
    assert search(ItemType.AUTOMATION, "automation.floor") == {
        ItemType.FLOOR: {first_floor.floor_id},
    }
    assert search(ItemType.AUTOMATION, "automation.area") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.FLOOR: {first_floor.floor_id},
    }
    assert search(ItemType.AUTOMATION, "automation.group") == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id, kitchen_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            "group.wled_hue",
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.GROUP: {"group.wled_hue"},
        ItemType.INTEGRATION: {"hue", "wled"},
    }
    assert search(ItemType.AUTOMATION, "automation.scene") == {
        ItemType.AREA: {bedroom_area.id, kitchen_area.id, living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            scene_wled_hue_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
    }
    assert search(ItemType.AUTOMATION, "automation.script") == {
        ItemType.AREA: {bedroom_area.id, kitchen_area.id, living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            scene_wled_hue_entity.entity_id,
            script_scene_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id},
    }

    assert not search(ItemType.AUTOMATION_BLUEPRINT, "unknown.yaml")
    assert search(ItemType.AUTOMATION_BLUEPRINT, "test_event_service.yaml") == {
        ItemType.AUTOMATION: {
            "automation.blueprint_automation_1",
            "automation.blueprint_automation_2",
        }
    }

    assert not search(ItemType.CONFIG_ENTRY, "unknown")
    assert search(ItemType.CONFIG_ENTRY, hue_config_entry.entry_id) == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.ENTITY: {
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.hue", "group.wled_hue"},
        ItemType.INTEGRATION: {"hue"},
        ItemType.SCENE: {"scene.scene_hue_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.device", "script.hue"},
    }
    assert search(ItemType.CONFIG_ENTRY, wled_config_entry.entry_id) == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id},
        ItemType.AUTOMATION: {"automation.wled_entity", "automation.wled_device"},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.INTEGRATION: {"wled"},
        ItemType.SCENE: {"scene.scene_wled_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.wled"},
    }

    assert not search(ItemType.DEVICE, "unknown")
    assert search(ItemType.DEVICE, wled_device.id) == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id},
        ItemType.AUTOMATION: {"automation.wled_entity", "automation.wled_device"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.INTEGRATION: {"wled"},
        ItemType.LABEL: {label_christmas.label_id},
        ItemType.SCENE: {"scene.scene_wled_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.wled"},
    }
    assert search(ItemType.DEVICE, hue_device.id) == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.ENTITY: {
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.hue", "group.wled_hue"},
        ItemType.INTEGRATION: {"hue"},
        ItemType.SCENE: {"scene.scene_hue_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.device", "script.hue"},
    }

    assert not search(ItemType.ENTITY, "sensor.unknown")
    assert search(ItemType.ENTITY, wled_segment_1_entity.entity_id) == {
        ItemType.AREA: {living_room_area.id},
        ItemType.AUTOMATION: {"automation.wled_entity"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.INTEGRATION: {"wled"},
        ItemType.SCENE: {"scene.scene_wled_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.wled"},
    }
    assert search(ItemType.ENTITY, wled_segment_2_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.INTEGRATION: {"wled"},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
    }
    assert search(ItemType.ENTITY, hue_segment_1_entity.entity_id) == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.hue", "group.wled_hue"},
        ItemType.INTEGRATION: {"hue"},
        ItemType.LABEL: {label_energy.label_id},
        ItemType.SCENE: {"scene.scene_hue_seg_1", scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.hue"},
    }
    assert search(ItemType.ENTITY, hue_segment_2_entity.entity_id) == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.GROUP: {"group.hue", "group.wled_hue"},
        ItemType.INTEGRATION: {"hue"},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
    }
    assert not search(ItemType.ENTITY, "automation.wled")
    assert search(ItemType.ENTITY, script_scene_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.AUTOMATION: {"automation.script"},
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.LABEL: {label_other.label_id},
        ItemType.SCRIPT: {"script.nested"},
    }
    assert search(ItemType.ENTITY, "group.wled_hue") == {
        ItemType.AUTOMATION: {"automation.group"},
        ItemType.SCRIPT: {"script.group"},
    }
    assert search(ItemType.ENTITY, person_paulus_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.LABEL: {label_other.label_id},
    }
    assert search(ItemType.ENTITY, scene_wled_hue_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.AUTOMATION: {"automation.scene"},
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.LABEL: {label_other.label_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id},
    }
    assert search(ItemType.ENTITY, "device_tracker.paulus_iphone") == {
        ItemType.PERSON: {person_paulus_entity.entity_id},
    }
    assert search(ItemType.ENTITY, "light.wled_config_entry_source") == {
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.INTEGRATION: {"wled"},
    }

    assert not search(ItemType.FLOOR, "unknown")
    assert search(ItemType.FLOOR, first_floor.floor_id) == {
        ItemType.AREA: {kitchen_area.id, living_room_area.id},
        ItemType.AUTOMATION: {
            "automation.area",
            "automation.floor",
            "automation.wled_device",
            "automation.wled_entity",
        },
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id, wled_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id, wled_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.GROUP: {"group.hue", "group.wled", "group.wled_hue"},
        ItemType.SCENE: {
            "scene.scene_hue_seg_1",
            "scene.scene_wled_seg_1",
            scene_wled_hue_entity.entity_id,
        },
        ItemType.SCRIPT: {
            "script.device",
            "script.area",
            "script.floor",
            "script.hue",
            "script.wled",
        },
    }
    assert search(ItemType.FLOOR, second_floor.floor_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.AUTOMATION: {"automation.scene", "automation.script"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.ENTITY: {
            wled_segment_2_entity.entity_id,
            person_paulus_entity.entity_id,
            scene_wled_hue_entity.entity_id,
            script_scene_entity.entity_id,
        },
        ItemType.GROUP: {"group.wled", "group.wled_hue"},
        ItemType.PERSON: {person_paulus_entity.entity_id},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id, "script.nested"},
    }

    assert not search(ItemType.GROUP, "group.unknown")
    assert search(ItemType.GROUP, "group.wled") == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"wled"},
    }
    assert search(ItemType.GROUP, "group.hue") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.ENTITY: {
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"hue"},
    }
    assert search(ItemType.GROUP, "group.wled_hue") == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id, kitchen_area.id},
        ItemType.AUTOMATION: {"automation.group"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.SCRIPT: {"script.group"},
    }

    assert not search(ItemType.LABEL, "unknown")
    assert search(ItemType.LABEL, label_christmas.label_id) == {
        ItemType.AUTOMATION: {"automation.label"},
        ItemType.DEVICE: {wled_device.id},
    }
    assert search(ItemType.LABEL, label_energy.label_id) == {
        ItemType.ENTITY: {hue_segment_1_entity.entity_id},
    }
    assert search(ItemType.LABEL, label_other.label_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.ENTITY: {
            scene_wled_hue_entity.entity_id,
            person_paulus_entity.entity_id,
            script_scene_entity.entity_id,
        },
        ItemType.PERSON: {person_paulus_entity.entity_id},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {"script.label", script_scene_entity.entity_id},
    }

    assert not search(ItemType.PERSON, "person.unknown")
    assert search(ItemType.PERSON, person_paulus_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id},
        ItemType.ENTITY: {"device_tracker.paulus_iphone"},
        ItemType.FLOOR: {second_floor.floor_id},
        ItemType.LABEL: {label_other.label_id},
    }

    assert not search(ItemType.SCENE, "scene.unknown")
    assert search(ItemType.SCENE, "scene.scene_wled_seg_1") == {
        ItemType.AREA: {living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {wled_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"wled"},
    }
    assert search(ItemType.SCENE, "scene.scene_hue_seg_1") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.ENTITY: {hue_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"hue"},
    }
    assert search(ItemType.SCENE, scene_wled_hue_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id, kitchen_area.id},
        ItemType.AUTOMATION: {"automation.scene"},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.LABEL: {label_other.label_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id},
    }

    assert not search(ItemType.SCRIPT, "script.unknown")
    assert search(ItemType.SCRIPT, "script.blueprint_script_1") == {
        ItemType.ENTITY: {"light.kitchen"},
        ItemType.SCRIPT_BLUEPRINT: {"test_service.yaml"},
    }
    assert search(ItemType.SCRIPT, "script.blueprint_script_2") == {
        ItemType.ENTITY: {"light.kitchen"},
        ItemType.SCRIPT_BLUEPRINT: {"test_service.yaml"},
    }
    assert search(ItemType.SCRIPT, "script.wled") == {
        ItemType.AREA: {living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id},
        ItemType.ENTITY: {wled_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"wled"},
    }
    assert search(ItemType.SCRIPT, "script.hue") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.ENTITY: {hue_segment_1_entity.entity_id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"hue"},
    }
    assert search(ItemType.SCRIPT, "script.script_with_templated_services") == {}
    assert search(ItemType.SCRIPT, "script.device") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.CONFIG_ENTRY: {hue_config_entry.entry_id},
        ItemType.DEVICE: {hue_device.id},
        ItemType.FLOOR: {first_floor.floor_id},
        ItemType.INTEGRATION: {"hue"},
    }
    assert search(ItemType.SCRIPT, "script.floor") == {
        ItemType.FLOOR: {first_floor.floor_id},
    }
    assert search(ItemType.SCRIPT, "script.area") == {
        ItemType.AREA: {kitchen_area.id},
        ItemType.FLOOR: {first_floor.floor_id},
    }
    assert search(ItemType.SCRIPT, "script.group") == {
        ItemType.AREA: {bedroom_area.id, living_room_area.id, kitchen_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            "group.wled_hue",
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.GROUP: {"group.wled_hue"},
        ItemType.INTEGRATION: {"hue", "wled"},
    }
    assert search(ItemType.SCRIPT, script_scene_entity.entity_id) == {
        ItemType.AREA: {bedroom_area.id, kitchen_area.id, living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            scene_wled_hue_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.LABEL: {label_other.label_id},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
    }
    assert search(ItemType.SCRIPT, "script.nested") == {
        ItemType.AREA: {bedroom_area.id, kitchen_area.id, living_room_area.id},
        ItemType.CONFIG_ENTRY: {wled_config_entry.entry_id, hue_config_entry.entry_id},
        ItemType.DEVICE: {wled_device.id, hue_device.id},
        ItemType.ENTITY: {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            scene_wled_hue_entity.entity_id,
            script_scene_entity.entity_id,
        },
        ItemType.FLOOR: {first_floor.floor_id, second_floor.floor_id},
        ItemType.INTEGRATION: {"hue", "wled"},
        ItemType.SCENE: {scene_wled_hue_entity.entity_id},
        ItemType.SCRIPT: {script_scene_entity.entity_id},
    }

    assert not search(ItemType.SCRIPT_BLUEPRINT, "unknown.yaml")
    assert search(ItemType.SCRIPT_BLUEPRINT, "test_service.yaml") == {
        ItemType.SCRIPT: {"script.blueprint_script_1", "script.blueprint_script_2"},
    }

    # WebSocket
    client = await hass_ws_client(hass)
    await client.send_json(
        {
            "id": 1,
            "type": "search/related",
            "item_type": "device",
            "item_id": hue_device.id,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert response["result"] == {
        ItemType.AREA: [kitchen_area.id],
        ItemType.ENTITY: unordered(
            [
                hue_segment_1_entity.entity_id,
                hue_segment_2_entity.entity_id,
            ]
        ),
        ItemType.GROUP: unordered(
            [
                "group.hue",
                "group.wled_hue",
            ]
        ),
        ItemType.CONFIG_ENTRY: [hue_config_entry.entry_id],
        ItemType.FLOOR: [first_floor.floor_id],
        ItemType.INTEGRATION: ["hue"],
        ItemType.SCENE: unordered(
            ["scene.scene_hue_seg_1", scene_wled_hue_entity.entity_id]
        ),
        ItemType.SCRIPT: unordered(["script.device", "script.hue"]),
    }
