"""Tests for the Group websocket API."""

from homeassistant.components import group
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


async def test_groups_for_entity(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test listing compatible groups for an entity."""
    hass.states.async_set("light.one", "on")
    hass.states.async_set("light.two", "on")
    hass.states.async_set("switch.one", "on")

    light_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["light.one"],
            "group_type": "light",
            "hide_members": False,
            "name": "Kitchen lights",
        },
        title="Kitchen lights",
    )
    light_group.add_to_hass(hass)

    switch_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["switch.one"],
            "group_type": "switch",
            "hide_members": False,
            "name": "Kitchen switches",
        },
        title="Kitchen switches",
    )
    switch_group.add_to_hass(hass)

    assert await async_setup_component(hass, group.DOMAIN, {})
    await hass.async_block_till_done()

    unloaded_light_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["light.one"],
            "group_type": "light",
            "hide_members": False,
            "name": "Unloaded lights",
        },
        title="Unloaded lights",
    )
    unloaded_light_group.add_to_hass(hass)

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "group/groups_for_entity", "entity_id": "light.two"}
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "group_type": "light",
        "groups": [
            {
                "entry_id": light_group.entry_id,
                "entity_id": "light.kitchen_lights",
                "name": "Kitchen lights",
            },
            {
                "entry_id": unloaded_light_group.entry_id,
                "entity_id": None,
                "name": "Unloaded lights",
            },
        ],
    }


async def test_add_entity_to_group(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test adding an entity to a group."""
    hass.states.async_set("light.one", "on")
    hass.states.async_set("light.two", "off")

    light_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["light.one"],
            "group_type": "light",
            "hide_members": False,
            "name": "Kitchen lights",
        },
        title="Kitchen lights",
    )
    light_group.add_to_hass(hass)

    assert await async_setup_component(hass, group.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "group/add_entity",
            "entry_id": light_group.entry_id,
            "entity_id": "light.two",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"entities": ["light.one", "light.two"]}
    assert light_group.options["entities"] == ["light.one", "light.two"]
    assert hass.states.get("light.kitchen_lights").attributes["entity_id"] == [
        "light.one",
        "light.two",
    ]


async def test_add_entity_to_group_hides_member(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test adding an entity to a group hides the entity if requested."""
    hass.states.async_set("light.one", "on")
    entity_entry = entity_registry.async_get_or_create(
        "light", "test", "two", suggested_object_id="two"
    )
    hass.states.async_set(entity_entry.entity_id, "off")

    light_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["light.one"],
            "group_type": "light",
            "hide_members": True,
            "name": "Kitchen lights",
        },
        title="Kitchen lights",
    )
    light_group.add_to_hass(hass)

    assert await async_setup_component(hass, group.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "group/add_entity",
            "entry_id": light_group.entry_id,
            "entity_id": entity_entry.entity_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {"entities": ["light.one", "light.two"]}
    assert entity_registry.async_get(entity_entry.entity_id).hidden_by is (
        er.RegistryEntryHider.INTEGRATION
    )


async def test_add_incompatible_entity_to_group(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test adding an incompatible entity to a group."""
    hass.states.async_set("light.one", "on")
    hass.states.async_set("switch.one", "on")

    light_group = MockConfigEntry(
        domain=group.DOMAIN,
        options={
            "all": False,
            "entities": ["light.one"],
            "group_type": "light",
            "hide_members": False,
            "name": "Kitchen lights",
        },
        title="Kitchen lights",
    )
    light_group.add_to_hass(hass)

    assert await async_setup_component(hass, group.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "group/add_entity",
            "entry_id": light_group.entry_id,
            "entity_id": "switch.one",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "invalid_entity"
    assert light_group.options["entities"] == ["light.one"]
