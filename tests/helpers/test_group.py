"""Test the group helper."""


from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import group


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
