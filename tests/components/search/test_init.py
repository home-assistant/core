"""Tests for Search integration."""
import pytest

from homeassistant.components import search
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity,
    entity_registry as er,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


MOCK_ENTITY_SOURCES = {
    "light.platform_config_source": {
        "source": entity.SOURCE_PLATFORM_CONFIG,
        "domain": "wled",
    },
    "light.config_entry_source": {
        "source": entity.SOURCE_CONFIG_ENTRY,
        "config_entry": "config_entry_id",
        "domain": "wled",
    },
}


async def test_search(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that search works."""
    living_room_area = area_registry.async_create("Living Room")

    # Light strip with 2 lights.
    wled_config_entry = MockConfigEntry(domain="wled")
    wled_config_entry.add_to_hass(hass)

    wled_device = device_registry.async_get_or_create(
        config_entry_id=wled_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"wled", "wled-1"}),
    )

    device_registry.async_update_device(wled_device.id, area_id=living_room_area.id)

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

    entity_sources = {
        "light.wled_platform_config_source": {
            "source": entity.SOURCE_PLATFORM_CONFIG,
            "domain": "wled",
        },
        "light.wled_config_entry_source": {
            "source": entity.SOURCE_CONFIG_ENTRY,
            "config_entry": wled_config_entry.entry_id,
            "domain": "wled",
        },
    }

    # Non related info.
    kitchen_area = area_registry.async_create("Kitchen")

    hue_config_entry = MockConfigEntry(domain="hue")
    hue_config_entry.add_to_hass(hass)

    hue_device = device_registry.async_get_or_create(
        config_entry_id=hue_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"hue", "hue-1"}),
    )

    device_registry.async_update_device(hue_device.id, area_id=kitchen_area.id)

    hue_segment_1_entity = entity_registry.async_get_or_create(
        "light",
        "hue",
        "hue-1-seg-1",
        suggested_object_id="hue segment 1",
        config_entry=hue_config_entry,
        device_id=hue_device.id,
    )
    hue_segment_2_entity = entity_registry.async_get_or_create(
        "light",
        "hue",
        "hue-1-seg-2",
        suggested_object_id="hue segment 2",
        config_entry=hue_config_entry,
        device_id=hue_device.id,
    )

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

    await async_setup_component(
        hass,
        "script",
        {
            "script": {
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
            }
        },
    )

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
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
            ]
        },
    )

    # Ensure automations set up correctly.
    assert hass.states.get("automation.wled_entity") is not None
    assert hass.states.get("automation.wled_device") is not None

    # Explore the graph from every node and make sure we find the same results
    expected = {
        "config_entry": {wled_config_entry.entry_id},
        "area": {living_room_area.id},
        "device": {wled_device.id},
        "entity": {wled_segment_1_entity.entity_id, wled_segment_2_entity.entity_id},
        "scene": {"scene.scene_wled_seg_1", "scene.scene_wled_hue"},
        "group": {"group.wled", "group.wled_hue"},
        "script": {"script.wled"},
        "automation": {"automation.wled_entity", "automation.wled_device"},
    }

    for search_type, search_id in (
        ("config_entry", wled_config_entry.entry_id),
        ("area", living_room_area.id),
        ("device", wled_device.id),
        ("entity", wled_segment_1_entity.entity_id),
        ("entity", wled_segment_2_entity.entity_id),
        ("scene", "scene.scene_wled_seg_1"),
        ("group", "group.wled"),
        ("script", "script.wled"),
        ("automation", "automation.wled_entity"),
        ("automation", "automation.wled_device"),
    ):
        searcher = search.Searcher(
            hass, device_registry, entity_registry, entity_sources
        )
        results = searcher.async_search(search_type, search_id)
        # Add the item we searched for, it's omitted from results
        results.setdefault(search_type, set()).add(search_id)

        assert (
            results == expected
        ), f"Results for {search_type}/{search_id} do not match up"

    # For combined things, needs to return everything.
    expected_combined = {
        "config_entry": {wled_config_entry.entry_id, hue_config_entry.entry_id},
        "area": {living_room_area.id, kitchen_area.id},
        "device": {wled_device.id, hue_device.id},
        "entity": {
            wled_segment_1_entity.entity_id,
            wled_segment_2_entity.entity_id,
            hue_segment_1_entity.entity_id,
            hue_segment_2_entity.entity_id,
        },
        "scene": {
            "scene.scene_wled_seg_1",
            "scene.scene_hue_seg_1",
            "scene.scene_wled_hue",
        },
        "group": {"group.wled", "group.hue", "group.wled_hue"},
        "script": {"script.wled", "script.hue"},
        "automation": {"automation.wled_entity", "automation.wled_device"},
    }
    for search_type, search_id in (
        ("scene", "scene.scene_wled_hue"),
        ("group", "group.wled_hue"),
    ):
        searcher = search.Searcher(
            hass, device_registry, entity_registry, entity_sources
        )
        results = searcher.async_search(search_type, search_id)
        # Add the item we searched for, it's omitted from results
        results.setdefault(search_type, set()).add(search_id)
        assert (
            results == expected_combined
        ), f"Results for {search_type}/{search_id} do not match up"

    for search_type, search_id in (
        ("entity", "automation.non_existing"),
        ("entity", "scene.non_existing"),
        ("entity", "group.non_existing"),
        ("entity", "script.non_existing"),
        ("entity", "light.non_existing"),
        ("area", "non_existing"),
        ("config_entry", "non_existing"),
        ("device", "non_existing"),
        ("group", "group.non_existing"),
        ("scene", "scene.non_existing"),
        ("script", "script.non_existing"),
        ("automation", "automation.non_existing"),
    ):
        searcher = search.Searcher(
            hass, device_registry, entity_registry, entity_sources
        )
        assert searcher.async_search(search_type, search_id) == {}

    # Test search of templated script. We can't find referenced areas, devices or
    # entities within templated services, but searching them should not raise or
    # otherwise fail.
    assert hass.states.get("script.script_with_templated_services")
    for search_type, search_id in (
        ("area", "script.script_with_templated_services"),
        ("device", "script.script_with_templated_services"),
        ("entity", "script.script_with_templated_services"),
    ):
        searcher = search.Searcher(
            hass, device_registry, entity_registry, entity_sources
        )
        assert searcher.async_search(search_type, search_id) == {}

    searcher = search.Searcher(hass, device_registry, entity_registry, entity_sources)
    assert searcher.async_search("entity", "light.wled_config_entry_source") == {
        "config_entry": {wled_config_entry.entry_id},
    }


async def test_area_lookup(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test area based lookup."""
    living_room_area = area_registry.async_create("Living Room")

    await async_setup_component(
        hass,
        "script",
        {
            "script": {
                "wled": {
                    "sequence": [
                        {
                            "service": "light.turn_on",
                            "target": {"area_id": living_room_area.id},
                        },
                    ]
                },
            }
        },
    )

    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "area_turn_on",
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": [
                        {
                            "service": "light.turn_on",
                            "data": {
                                "area_id": living_room_area.id,
                            },
                        },
                    ],
                },
            ]
        },
    )

    searcher = search.Searcher(
        hass, device_registry, entity_registry, MOCK_ENTITY_SOURCES
    )
    assert searcher.async_search("area", living_room_area.id) == {
        "script": {"script.wled"},
        "automation": {"automation.area_turn_on"},
    }

    searcher = search.Searcher(
        hass, device_registry, entity_registry, MOCK_ENTITY_SOURCES
    )
    assert searcher.async_search("automation", "automation.area_turn_on") == {
        "area": {living_room_area.id},
    }


async def test_person_lookup(hass: HomeAssistant) -> None:
    """Test searching persons."""
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

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("entity", "device_tracker.paulus_iphone") == {
        "person": {"person.paulus"},
    }

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("entity", "person.paulus") == {
        "entity": {"device_tracker.paulus_iphone"},
    }


async def test_automation_blueprint(hass):
    """Test searching for automation blueprints."""

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
            ]
        },
    )

    # Ensure automations set up correctly.
    assert hass.states.get("automation.blueprint_automation_1") is not None
    assert hass.states.get("automation.blueprint_automation_1") is not None

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("automation", "automation.blueprint_automation_1") == {
        "automation": {"automation.blueprint_automation_2"},
        "automation_blueprint": {"test_event_service.yaml"},
        "entity": {"light.kitchen"},
    }

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("automation_blueprint", "test_event_service.yaml") == {
        "automation": {
            "automation.blueprint_automation_1",
            "automation.blueprint_automation_2",
        },
    }


async def test_script_blueprint(hass):
    """Test searching for script blueprints."""

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
            }
        },
    )

    # Ensure automations set up correctly.
    assert hass.states.get("script.blueprint_script_1") is not None
    assert hass.states.get("script.blueprint_script_1") is not None

    device_reg = dr.async_get(hass)
    entity_reg = er.async_get(hass)

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("script", "script.blueprint_script_1") == {
        "entity": {"light.kitchen"},
        "script": {"script.blueprint_script_2"},
        "script_blueprint": {"test_service.yaml"},
    }

    searcher = search.Searcher(hass, device_reg, entity_reg, MOCK_ENTITY_SOURCES)
    assert searcher.async_search("script_blueprint", "test_service.yaml") == {
        "script": {"script.blueprint_script_1", "script.blueprint_script_2"},
    }


async def test_ws_api(hass: HomeAssistant, hass_ws_client: WebSocketGenerator) -> None:
    """Test WS API."""
    assert await async_setup_component(hass, "search", {})

    area_reg = ar.async_get(hass)
    device_reg = dr.async_get(hass)

    kitchen_area = area_reg.async_create("Kitchen")

    hue_config_entry = MockConfigEntry(domain="hue")
    hue_config_entry.add_to_hass(hass)

    hue_device = device_reg.async_get_or_create(
        config_entry_id=hue_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"hue", "hue-1"}),
    )

    device_reg.async_update_device(hue_device.id, area_id=kitchen_area.id)

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
        "config_entry": [hue_config_entry.entry_id],
        "area": [kitchen_area.id],
    }
