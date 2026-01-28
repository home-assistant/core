"""Test the group helper."""

from homeassistant.const import ATTR_ENTITY_ID, ATTR_GROUP_ENTITIES, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, group
from homeassistant.helpers.group import (
    GenericGroup,
    IntegrationSpecificGroup,
    get_group_entities,
)

from tests.common import MockEntity, MockEntityPlatform


async def test_expand_entity_ids(hass: HomeAssistant) -> None:
    """Test expand_entity_ids method."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set(
        "group.init_group", STATE_ON, {ATTR_ENTITY_ID: ["light.bowl", "light.ceiling"]}
    )
    state = hass.states.get("group.init_group")
    assert state is not None
    assert state.attributes[ATTR_ENTITY_ID] == ["light.bowl", "light.ceiling"]

    assert sorted(group.expand_entity_ids(hass, ["group.init_group"])) == [
        "light.bowl",
        "light.ceiling",
    ]
    assert sorted(group.expand_entity_ids(hass, ["group.INIT_group"])) == [
        "light.bowl",
        "light.ceiling",
    ]


async def test_expand_entity_ids_does_not_return_duplicates(
    hass: HomeAssistant,
) -> None:
    """Test that expand_entity_ids does not return duplicates."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set(
        "group.init_group", STATE_ON, {ATTR_ENTITY_ID: ["light.bowl", "light.ceiling"]}
    )

    assert sorted(
        group.expand_entity_ids(hass, ["group.init_group", "light.Ceiling"])
    ) == ["light.bowl", "light.ceiling"]

    assert sorted(
        group.expand_entity_ids(hass, ["light.bowl", "group.init_group"])
    ) == ["light.bowl", "light.ceiling"]


async def test_expand_entity_ids_recursive(hass: HomeAssistant) -> None:
    """Test expand_entity_ids method with a group that contains itself."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set(
        "group.init_group", STATE_ON, {ATTR_ENTITY_ID: ["light.bowl", "light.ceiling"]}
    )

    hass.states.async_set(
        "group.rec_group",
        STATE_ON,
        {ATTR_ENTITY_ID: ["group.init_group", "light.ceiling"]},
    )

    assert sorted(group.expand_entity_ids(hass, ["group.rec_group"])) == [
        "light.bowl",
        "light.ceiling",
    ]


async def test_expand_entity_ids_ignores_non_strings(hass: HomeAssistant) -> None:
    """Test that non string elements in lists are ignored."""
    assert group.expand_entity_ids(hass, [5, True]) == []


async def test_get_entity_ids(hass: HomeAssistant) -> None:
    """Test get_entity_ids method."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set(
        "group.init_group", STATE_ON, {ATTR_ENTITY_ID: ["light.bowl", "light.ceiling"]}
    )

    assert sorted(group.get_entity_ids(hass, "group.init_group")) == [
        "light.bowl",
        "light.ceiling",
    ]


async def test_get_entity_ids_with_domain_filter(hass: HomeAssistant) -> None:
    """Test if get_entity_ids works with a domain_filter."""
    hass.states.async_set("switch.AC", STATE_OFF)
    hass.states.async_set(
        "group.mixed_group", STATE_ON, {ATTR_ENTITY_ID: ["light.bowl", "switch.ac"]}
    )

    assert group.get_entity_ids(hass, "group.mixed_group", domain_filter="switch") == [
        "switch.ac"
    ]


async def test_get_entity_ids_with_non_existing_group_name(hass: HomeAssistant) -> None:
    """Test get_entity_ids with a non existing group."""
    assert group.get_entity_ids(hass, "non_existing") == []


async def test_get_entity_ids_with_non_group_state(hass: HomeAssistant) -> None:
    """Test get_entity_ids with a non group state."""
    assert group.get_entity_ids(hass, "switch.AC") == []


async def test_get_group_entities(hass: HomeAssistant) -> None:
    """Test get_group_entities returns registered group entities."""
    assert get_group_entities(hass) == {}

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.test_group", unique_id="test_group_1")
    ent.group = GenericGroup(ent, ["light.bulb1", "light.bulb2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    group_entities = get_group_entities(hass)
    assert "light.test_group" in group_entities
    assert group_entities["light.test_group"] is ent


async def test_group_entity_removed_from_registry(hass: HomeAssistant) -> None:
    """Test group entity is removed from get_group_entities on removal."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.test_group", unique_id="test_group_2")
    ent.group = GenericGroup(ent, ["light.bulb1", "light.bulb2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()
    assert "light.test_group" in get_group_entities(hass)

    await platform.async_remove_entity(ent.entity_id)
    await hass.async_block_till_done()
    assert "light.test_group" not in get_group_entities(hass)


async def test_multiple_group_entities(hass: HomeAssistant) -> None:
    """Test multiple group entities can be registered and work independently."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent1 = MockEntity(entity_id="light.group1", unique_id="multi_1")
    ent1.group = GenericGroup(ent1, ["light.a", "light.b"])

    ent2 = MockEntity(entity_id="light.group2", unique_id="multi_2")
    ent2.group = GenericGroup(ent2, ["light.c", "light.d"])

    await platform.async_add_entities([ent1, ent2])
    await hass.async_block_till_done()

    group_entities = get_group_entities(hass)
    assert "light.group1" in group_entities
    assert "light.group2" in group_entities

    expanded1 = group.expand_entity_ids(hass, ["light.group1"])
    expanded2 = group.expand_entity_ids(hass, ["light.group2"])

    assert sorted(expanded1) == ["light.a", "light.b"]
    assert sorted(expanded2) == ["light.c", "light.d"]


async def test_generic_group_included_entity_ids(hass: HomeAssistant) -> None:
    """Test GenericGroup included_entity_ids property."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.test_group")
    ent.group = GenericGroup(ent, ["light.bulb1", "light.bulb2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    assert ent.group.included_entity_ids == ["light.bulb1", "light.bulb2"]


async def test_expand_entity_ids_with_generic_group(hass: HomeAssistant) -> None:
    """Test expand_entity_ids with GenericGroup entities."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.living_room_group", unique_id="living_room")
    ent.group = GenericGroup(ent, ["light.lamp1", "light.lamp2", "light.lamp3"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    hass.states.async_set("light.lamp1", STATE_ON)
    hass.states.async_set("light.lamp2", STATE_OFF)
    hass.states.async_set("light.lamp3", STATE_ON)

    expanded = group.expand_entity_ids(hass, ["light.living_room_group"])
    assert sorted(expanded) == ["light.lamp1", "light.lamp2", "light.lamp3"]


async def test_expand_entity_ids_with_generic_group_recursive(
    hass: HomeAssistant,
) -> None:
    """Test expand_entity_ids with nested GenericGroup entities."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    inner_group = MockEntity(entity_id="light.inner_group", unique_id="inner")
    inner_group.group = GenericGroup(inner_group, ["light.lamp1", "light.lamp2"])

    outer_group = MockEntity(entity_id="light.outer_group", unique_id="outer")
    outer_group.group = GenericGroup(outer_group, ["light.inner_group", "light.lamp3"])

    await platform.async_add_entities([inner_group, outer_group])
    await hass.async_block_till_done()

    expanded = group.expand_entity_ids(hass, ["light.outer_group"])
    assert sorted(expanded) == ["light.lamp1", "light.lamp2", "light.lamp3"]


async def test_expand_entity_ids_with_generic_group_self_reference(
    hass: HomeAssistant,
) -> None:
    """Test expand_entity_ids handles GenericGroup with self-reference."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.self_ref_group", unique_id="self_ref")
    ent.group = GenericGroup(
        ent, ["light.self_ref_group", "light.bulb1", "light.bulb2"]
    )

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    expanded = group.expand_entity_ids(hass, ["light.self_ref_group"])
    assert sorted(expanded) == ["light.bulb1", "light.bulb2"]


async def test_entity_group_attribute_in_state(hass: HomeAssistant) -> None:
    """Test ATTR_GROUP_ENTITIES is included in entity state attributes."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.group_with_attrs", unique_id="attrs_test")
    ent.group = GenericGroup(ent, ["light.lamp1", "light.lamp2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    state = hass.states.get("light.group_with_attrs")
    assert state is not None
    assert ATTR_GROUP_ENTITIES in state.attributes
    assert state.attributes[ATTR_GROUP_ENTITIES] == ["light.lamp1", "light.lamp2"]


async def test_integration_specific_group_included_entity_ids(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup resolves entity IDs from unique IDs."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.integration_group", unique_id="int_group")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1", "unique_2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    assert sorted(ent.group.included_entity_ids) == ["light.member1", "light.member2"]


async def test_integration_specific_group_missing_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup handles missing entities."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.partial_group", unique_id="partial")
    ent.group = IntegrationSpecificGroup(
        ent, ["unique_1", "unique_2", "unique_missing"]
    )

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    assert ent.group.included_entity_ids == ["light.member1"]


async def test_integration_specific_group_included_unique_ids_setter(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup included_unique_ids setter clears cache."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_3", suggested_object_id="member3"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.dynamic_group", unique_id="dynamic")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()
    assert ent.group.included_entity_ids == ["light.member1"]

    ent.group.included_unique_ids = ["unique_2", "unique_3"]

    assert sorted(ent.group.included_entity_ids) == ["light.member2", "light.member3"]


async def test_integration_specific_group_member_added(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup updates when member is added to registry."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.registry_group", unique_id="reg_group")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1", "unique_2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()
    assert ent.group.included_entity_ids == ["light.member1"]

    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )
    await hass.async_block_till_done()

    assert sorted(ent.group.included_entity_ids) == ["light.member1", "light.member2"]


async def test_integration_specific_group_member_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup updates when member is removed from registry."""
    entry1 = entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.remove_group", unique_id="rem_group")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1", "unique_2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    assert sorted(ent.group.included_entity_ids) == ["light.member1", "light.member2"]

    entity_registry.async_remove(entry1.entity_id)
    await hass.async_block_till_done()

    assert ent.group.included_entity_ids == ["light.member2"]


async def test_integration_specific_group_member_renamed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test IntegrationSpecificGroup updates when member entity_id is renamed."""
    entry = entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="original_name"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.group", unique_id="grp")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()
    assert ent.group.included_entity_ids == ["light.original_name"]

    entity_registry.async_update_entity(entry.entity_id, new_entity_id="light.new_name")
    await hass.async_block_till_done()

    assert ent.group.included_entity_ids == ["light.new_name"]


async def test_integration_specific_group_attribute_in_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test ATTR_GROUP_ENTITIES is included in IntegrationSpecificGroup state."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.int_group_attrs", unique_id="int_attrs")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1", "unique_2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    state = hass.states.get("light.int_group_attrs")
    assert state is not None
    assert ATTR_GROUP_ENTITIES in state.attributes
    assert sorted(state.attributes[ATTR_GROUP_ENTITIES]) == [
        "light.member1",
        "light.member2",
    ]


async def test_expand_entity_ids_integration_specific_group_not_expanded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test expand_entity_ids doesn't expand IntegrationSpecificGroup."""
    entity_registry.async_get_or_create(
        "light", "test", "unique_1", suggested_object_id="member1"
    )
    entity_registry.async_get_or_create(
        "light", "test", "unique_2", suggested_object_id="member2"
    )

    platform = MockEntityPlatform(hass, domain="light", platform_name="test")

    ent = MockEntity(entity_id="light.int_specific_group", unique_id="int_spec")
    ent.group = IntegrationSpecificGroup(ent, ["unique_1", "unique_2"])

    await platform.async_add_entities([ent])
    await hass.async_block_till_done()

    expanded = group.expand_entity_ids(hass, ["light.int_specific_group"])
    assert expanded == ["light.int_specific_group"]
