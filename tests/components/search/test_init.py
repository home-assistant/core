"""Tests for Search integration."""
from homeassistant.components import search
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa


async def test_search(hass):
    """Test that search works."""
    area_reg = await hass.helpers.area_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()
    entity_reg = await hass.helpers.entity_registry.async_get_registry()

    living_room_area = area_reg.async_create("Living Room")

    # Light strip with 2 lights.
    wled_config_entry = MockConfigEntry(domain="wled")
    wled_config_entry.add_to_hass(hass)

    wled_device = device_reg.async_get_or_create(
        config_entry_id=wled_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"wled", "wled-1"}),
    )

    device_reg.async_update_device(wled_device.id, area_id=living_room_area.id)

    wled_segment_1_entity = entity_reg.async_get_or_create(
        "light",
        "wled",
        "wled-1-seg-1",
        suggested_object_id="wled segment 1",
        config_entry=wled_config_entry,
        device_id=wled_device.id,
    )
    wled_segment_2_entity = entity_reg.async_get_or_create(
        "light",
        "wled",
        "wled-1-seg-2",
        suggested_object_id="wled segment 2",
        config_entry=wled_config_entry,
        device_id=wled_device.id,
    )

    # Non related info.
    kitchen_area = area_reg.async_create("Kitchen")

    hue_config_entry = MockConfigEntry(domain="hue")
    hue_config_entry.add_to_hass(hass)

    hue_device = device_reg.async_get_or_create(
        config_entry_id=hue_config_entry.entry_id,
        name="Light Strip",
        identifiers=({"hue", "hue-1"}),
    )

    device_reg.async_update_device(hue_device.id, area_id=kitchen_area.id)

    hue_segment_1_entity = entity_reg.async_get_or_create(
        "light",
        "hue",
        "hue-1-seg-1",
        suggested_object_id="hue segment 1",
        config_entry=hue_config_entry,
        device_id=hue_device.id,
    )
    hue_segment_2_entity = entity_reg.async_get_or_create(
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
        searcher = search.Searcher(hass, device_reg, entity_reg)
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
        searcher = search.Searcher(hass, device_reg, entity_reg)
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
        searcher = search.Searcher(hass, device_reg, entity_reg)
        assert searcher.async_search(search_type, search_id) == {}


async def test_ws_api(hass, hass_ws_client):
    """Test WS API."""
    assert await async_setup_component(hass, "search", {})

    area_reg = await hass.helpers.area_registry.async_get_registry()
    device_reg = await hass.helpers.device_registry.async_get_registry()

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
