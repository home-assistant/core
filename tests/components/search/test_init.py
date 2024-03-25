"""Tests for Search integration."""

import pytest
from pytest_unordered import unordered

from homeassistant.components.search import Searcher
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
        scene_wled_hue_entity.entity_id, area_id=bedroom_area.id
    )

    # Persons can technically be assigned to areas
    person_paulus_entity = entity_registry.async_get_or_create(
        "person",
        "person",
        "abcd",
        suggested_object_id="paulus",
    )
    entity_registry.async_update_entity(
        person_paulus_entity.entity_id, area_id=bedroom_area.id
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
                    "alias": "blueprint_automation_1",
                    "trigger": {"platform": "template", "value_template": "true"},
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
                    "trigger": {"platform": "template", "value_template": "true"},
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
                            "scene": "scene.scene_wled_hue",
                        },
                    ],
                },
                {
                    "alias": "script",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "script.turn_on",
                            "data": {"entity_id": "script.scene"},
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
                            "scene": "scene.scene_wled_hue",
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
                            "data": {"entity_id": "script.scene"},
                        },
                    ],
                },
            }
        },
    )

    def search(item_type: str, item_id: str) -> dict[str, set[str]]:
        """Search."""
        searcher = Searcher(
            hass, area_registry, device_registry, entity_registry, entity_sources
        )
        return searcher.async_search(item_type, item_id)

    #
    # Tests
    #
    assert not search("area", "unknown")
    assert search("area", bedroom_area.id) == {
        "automation": {"automation.scene", "automation.script"},
        "config_entry": {wled_config_entry.entry_id},
        "entity": {
            "light.wled_segment_2",
            "scene.scene_wled_hue",
            "script.scene",
            "person.paulus",
        },
        "floor": {second_floor.floor_id},
        "group": {"group.wled", "group.wled_hue"},
        "person": {"person.paulus"},
        "scene": {"scene.scene_wled_hue"},
        "script": {"script.scene", "script.nested"},
    }
    assert search("area", living_room_area.id) == {
        "automation": {"automation.wled_device"},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("area", kitchen_area.id) == {
        "automation": {"automation.area"},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "entity": {hue_segment_1_entity.entity_id, hue_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id},
        "script": {"script.area", "script.device"},
    }

    assert not search("automation", "automation.unknown")
    assert search("automation", "automation.blueprint_automation_1") == {
        "automation_blueprint": {"test_event_service.yaml"},
        "entity": {"light.kitchen"},
    }
    assert search("automation", "automation.blueprint_automation_2") == {
        "automation_blueprint": {"test_event_service.yaml"},
        "entity": {"light.kitchen"},
    }
    assert search("automation", "automation.wled_entity") == {
        "area": {living_room_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("automation", "automation.wled_device") == {
        "area": {living_room_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "floor": {first_floor.floor_id},
    }
    assert search("automation", "automation.floor") == {
        "floor": {first_floor.floor_id},
    }
    assert search("automation", "automation.area") == {
        "area": {kitchen_area.id},
        "floor": {first_floor.floor_id},
    }
    assert search("automation", "automation.group") == {
        "area": {bedroom_area.id, living_room_area.id, kitchen_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            "group.wled_hue",
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "group": {"group.wled_hue"},
    }
    assert search("automation", "automation.scene") == {
        "area": {bedroom_area.id, kitchen_area.id, living_room_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            "scene.scene_wled_hue",
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "scene": {"scene.scene_wled_hue"},
    }
    assert search("automation", "automation.script") == {
        "area": {bedroom_area.id, kitchen_area.id, living_room_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            "scene.scene_wled_hue",
            "script.scene",
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "scene": {"scene.scene_wled_hue"},
        "script": {"script.scene"},
    }

    assert not search("automation_blueprint", "unknown.yaml")
    assert search("automation_blueprint", "test_event_service.yaml") == {
        "automation": {
            "automation.blueprint_automation_1",
            "automation.blueprint_automation_2",
        }
    }

    assert not search("config_entry", "unknown")
    assert search("config_entry", hue_config_entry.entry_id) == {
        "area": {kitchen_area.id},
        "device": {hue_device.id},
        "entity": {hue_segment_1_entity.entity_id, hue_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id},
        "group": {"group.hue", "group.wled_hue"},
        "scene": {"scene.scene_hue_seg_1", "scene.scene_wled_hue"},
        "script": {"script.device", "script.hue"},
    }
    assert search("config_entry", wled_config_entry.entry_id) == {
        "area": {bedroom_area.id, living_room_area.id},
        "automation": {"automation.wled_entity", "automation.wled_device"},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id, wled_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "group": {"group.wled", "group.wled_hue"},
        "scene": {"scene.scene_wled_seg_1", "scene.scene_wled_hue"},
        "script": {"script.wled"},
    }

    assert not search("device", "unknown")
    assert search("device", wled_device.id) == {
        "area": {bedroom_area.id, living_room_area.id},
        "automation": {"automation.wled_entity", "automation.wled_device"},
        "config_entry": {wled_config_entry.entry_id},
        "entity": {wled_segment_1_entity.entity_id, wled_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "group": {"group.wled", "group.wled_hue"},
        "scene": {"scene.scene_wled_seg_1", "scene.scene_wled_hue"},
        "script": {"script.wled"},
    }
    assert search("device", hue_device.id) == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "entity": {hue_segment_1_entity.entity_id, hue_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id},
        "group": {"group.hue", "group.wled_hue"},
        "scene": {"scene.scene_hue_seg_1", "scene.scene_wled_hue"},
        "script": {"script.device", "script.hue"},
    }

    assert not search("entity", "sensor.unknown")
    assert search("entity", wled_segment_1_entity.entity_id) == {
        "area": {living_room_area.id},
        "automation": {"automation.wled_entity"},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "floor": {first_floor.floor_id},
        "group": {"group.wled", "group.wled_hue"},
        "scene": {"scene.scene_wled_seg_1", "scene.scene_wled_hue"},
        "script": {"script.wled"},
    }
    assert search("entity", wled_segment_2_entity.entity_id) == {
        "area": {bedroom_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "floor": {second_floor.floor_id},
        "group": {"group.wled", "group.wled_hue"},
        "scene": {"scene.scene_wled_hue"},
    }
    assert search("entity", hue_segment_1_entity.entity_id) == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "floor": {first_floor.floor_id},
        "group": {"group.hue", "group.wled_hue"},
        "scene": {"scene.scene_hue_seg_1", "scene.scene_wled_hue"},
        "script": {"script.hue"},
    }
    assert search("entity", hue_segment_2_entity.entity_id) == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "floor": {first_floor.floor_id},
        "group": {"group.hue", "group.wled_hue"},
        "scene": {"scene.scene_wled_hue"},
    }
    assert not search("entity", "automation.wled")
    assert search("entity", "script.scene") == {
        "area": {bedroom_area.id},
        "automation": {"automation.script"},
        "floor": {second_floor.floor_id},
        "script": {"script.nested"},
    }
    assert search("entity", "group.wled_hue") == {
        "automation": {"automation.group"},
        "script": {"script.group"},
    }
    assert search("entity", "person.paulus") == {
        "area": {bedroom_area.id},
        "floor": {second_floor.floor_id},
    }
    assert search("entity", "scene.scene_wled_hue") == {
        "area": {bedroom_area.id},
        "automation": {"automation.scene"},
        "floor": {second_floor.floor_id},
        "script": {"script.scene"},
    }
    assert search("entity", "device_tracker.paulus_iphone") == {
        "person": {"person.paulus"},
    }
    assert search("entity", "light.wled_config_entry_source") == {
        "config_entry": {wled_config_entry.entry_id},
    }

    assert not search("floor", "unknown")
    assert search("floor", first_floor.floor_id) == {
        "area": {kitchen_area.id, living_room_area.id},
        "automation": {"automation.area", "automation.wled_device"},
        "config_entry": {hue_config_entry.entry_id, wled_config_entry.entry_id},
        "device": {hue_device.id, wled_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "script": {"script.device", "script.area"},
    }
    assert search("floor", second_floor.floor_id) == {
        "area": {bedroom_area.id},
        "automation": {"automation.scene", "automation.script"},
        "config_entry": {wled_config_entry.entry_id},
        "entity": {
            wled_segment_2_entity.entity_id,
            "person.paulus",
            "scene.scene_wled_hue",
            "script.scene",
        },
        "group": {"group.wled", "group.wled_hue"},
        "person": {"person.paulus"},
        "scene": {"scene.scene_wled_hue"},
        "script": {"script.scene", "script.nested"},
    }

    assert not search("group", "group.unknown")
    assert search("group", "group.wled") == {
        "area": {bedroom_area.id, living_room_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id, wled_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id, second_floor.floor_id},
    }
    assert search("group", "group.hue") == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "entity": {hue_segment_1_entity.entity_id, hue_segment_2_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("group", "group.wled_hue") == {
        "area": {bedroom_area.id, living_room_area.id, kitchen_area.id},
        "automation": {"automation.group"},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "script": {"script.group"},
    }

    assert not search("label", "unknown")
    assert search("label", label_christmas.label_id) == {
        "automation": {"automation.label"},
        "device": {wled_device.id},
    }
    assert search("label", label_energy.label_id) == {
        "entity": {hue_segment_1_entity.entity_id},
    }
    assert search("label", label_other.label_id) == {
        "area": {bedroom_area.id},
        "entity": {"script.scene"},
        "script": {"script.label", "script.scene"},
    }

    assert not search("person", "person.unknown")
    assert search("person", "person.paulus") == {
        "area": {bedroom_area.id},
        "entity": {"device_tracker.paulus_iphone"},
        "floor": {second_floor.floor_id},
    }

    assert not search("scene", "scene.unknown")
    assert search("scene", "scene.scene_wled_seg_1") == {
        "area": {living_room_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("scene", "scene.scene_hue_seg_1") == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "entity": {hue_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("scene", "scene.scene_wled_hue") == {
        "area": {bedroom_area.id, living_room_area.id, kitchen_area.id},
        "automation": {"automation.scene"},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "script": {"script.scene"},
    }

    assert not search("script", "script.unknown")
    assert search("script", "script.blueprint_script_1") == {
        "entity": {"light.kitchen"},
        "script_blueprint": {"test_service.yaml"},
    }
    assert search("script", "script.blueprint_script_2") == {
        "entity": {"light.kitchen"},
        "script_blueprint": {"test_service.yaml"},
    }
    assert search("script", "script.wled") == {
        "area": {living_room_area.id},
        "config_entry": {wled_config_entry.entry_id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("script", "script.hue") == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "entity": {hue_segment_1_entity.entity_id},
        "floor": {first_floor.floor_id},
    }
    assert search("script", "script.script_with_templated_services") == {}
    assert search("script", "script.device") == {
        "area": {kitchen_area.id},
        "config_entry": {hue_config_entry.entry_id},
        "device": {hue_device.id},
        "floor": {first_floor.floor_id},
    }
    assert search("script", "script.floor") == {
        "floor": {first_floor.floor_id},
    }
    assert search("script", "script.area") == {
        "area": {kitchen_area.id},
        "floor": {first_floor.floor_id},
    }
    assert search("script", "script.group") == {
        "area": {bedroom_area.id, living_room_area.id, kitchen_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            "group.wled_hue",
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "group": {"group.wled_hue"},
    }
    assert search("script", "script.scene") == {
        "area": {bedroom_area.id, kitchen_area.id, living_room_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            "scene.scene_wled_hue",
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "scene": {"scene.scene_wled_hue"},
    }
    assert search("script", "script.nested") == {
        "area": {bedroom_area.id, kitchen_area.id, living_room_area.id},
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
            "scene.scene_wled_hue",
            "script.scene",
        },
        "floor": {first_floor.floor_id, second_floor.floor_id},
        "scene": {"scene.scene_wled_hue"},
        "script": {"script.scene"},
    }

    assert not search("script_blueprint", "unknown.yaml")
    assert search("script_blueprint", "test_service.yaml") == {
        "script": {"script.blueprint_script_1", "script.blueprint_script_2"},
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
        "area": [kitchen_area.id],
        "entity": unordered(
            [
                hue_segment_1_entity.entity_id,
                hue_segment_2_entity.entity_id,
            ]
        ),
        "group": unordered(
            [
                "group.hue",
                "group.wled_hue",
            ]
        ),
        "config_entry": [hue_config_entry.entry_id],
        "floor": [first_floor.floor_id],
        "scene": unordered(["scene.scene_hue_seg_1", "scene.scene_wled_hue"]),
        "script": unordered(["script.device", "script.hue"]),
    }
