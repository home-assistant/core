"""Tests for HomeKit target tracking."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.homekit.target import (
    async_is_bridge_target_entity,
    async_target_entity_ids_by_type,
    async_track_target_entity_change,
    should_include_entity,
)
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    label_registry as lr,
    target as target_helper,
)
from homeassistant.helpers.entityfilter import (
    CONF_EXCLUDE_DOMAINS,
    CONF_EXCLUDE_ENTITIES,
    CONF_EXCLUDE_ENTITY_GLOBS,
    CONF_INCLUDE_DOMAINS,
    CONF_INCLUDE_ENTITIES,
    CONF_INCLUDE_ENTITY_GLOBS,
)

from .util import async_fire_target_change_cooldown

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("include_rule", "exclude_rule", "expected"),
    [
        # A more-specific inclusion wins.
        ("entity", "device", True),
        ("device", "glob", True),
        ("glob", "area", True),
        ("area", "floor", True),
        ("floor", "label", True),
        ("label", "domain", True),
        # A more-specific exclusion wins.
        ("device", "entity", False),
        ("glob", "device", False),
        ("area", "glob", False),
        ("floor", "area", False),
        ("label", "floor", False),
        ("domain", "label", False),
        # Target exclusions win at equal specificity.
        ("entity", "entity", False),
        ("device", "device", False),
        ("area", "area", False),
        ("floor", "floor", False),
        ("label", "label", False),
        # Legacy base filter inclusions keep winning equal-specificity conflicts.
        ("glob", "glob", True),
        ("domain", "domain", True),
    ],
)
def test_target_filter_specificity(
    include_rule: str,
    exclude_rule: str,
    expected: bool,
) -> None:
    """Test specificity precedence and equal-specificity rules."""
    entity_id = "light.test"
    filter_config = {
        CONF_INCLUDE_DOMAINS: ["light"] if include_rule == "domain" else [],
        CONF_INCLUDE_ENTITIES: [],
        CONF_INCLUDE_ENTITY_GLOBS: ["light.*"] if include_rule == "glob" else [],
        CONF_EXCLUDE_DOMAINS: ["light"] if exclude_rule == "domain" else [],
        CONF_EXCLUDE_ENTITIES: [],
        CONF_EXCLUDE_ENTITY_GLOBS: ["light.*"] if exclude_rule == "glob" else [],
    }
    target_types = {
        "entity": ATTR_ENTITY_ID,
        "device": ATTR_DEVICE_ID,
        "area": ATTR_AREA_ID,
        "floor": ATTR_FLOOR_ID,
        "label": ATTR_LABEL_ID,
    }
    included_targets = (
        {target_types[include_rule]: {entity_id}}
        if include_rule in target_types
        else {}
    )
    excluded_targets = (
        {target_types[exclude_rule]: {entity_id}}
        if exclude_rule in target_types
        else {}
    )

    assert (
        should_include_entity(
            entity_id,
            filter_config,
            included_targets,
            excluded_targets,
            has_include_rules=True,
        )
        is expected
    )


def test_base_entity_filter_inclusion_wins_tie() -> None:
    """Test a legacy entity inclusion wins an equal exclusion."""
    entity_id = "light.test"
    filter_config = {
        CONF_INCLUDE_DOMAINS: [],
        CONF_INCLUDE_ENTITIES: [entity_id],
        CONF_INCLUDE_ENTITY_GLOBS: [],
        CONF_EXCLUDE_DOMAINS: [],
        CONF_EXCLUDE_ENTITIES: [entity_id],
        CONF_EXCLUDE_ENTITY_GLOBS: [],
    }

    assert should_include_entity(
        entity_id,
        filter_config,
        {},
        {},
        has_include_rules=True,
    )


def test_accessory_mode_target_expansion_is_filterable(
    hass: HomeAssistant,
) -> None:
    """Test accessory-mode entities can be filtered from target expansion."""
    hass.states.async_set("camera.test", "on")
    targets = {ATTR_ENTITY_ID: ["camera.test"]}

    assert (
        async_target_entity_ids_by_type(
            hass, targets, entity_filter=async_is_bridge_target_entity
        )[ATTR_ENTITY_ID]
        == set()
    )
    assert async_target_entity_ids_by_type(hass, targets)[ATTR_ENTITY_ID] == {
        "camera.test"
    }


def test_target_filter_with_only_exclusions() -> None:
    """Test exclude-only targets retain unmatched entities."""
    filter_config = {
        CONF_INCLUDE_DOMAINS: [],
        CONF_INCLUDE_ENTITIES: [],
        CONF_INCLUDE_ENTITY_GLOBS: [],
        CONF_EXCLUDE_DOMAINS: [],
        CONF_EXCLUDE_ENTITIES: [],
        CONF_EXCLUDE_ENTITY_GLOBS: [],
    }
    excluded_targets = {ATTR_LABEL_ID: {"light.private"}}

    assert not should_include_entity(
        "light.private",
        filter_config,
        {},
        excluded_targets,
        has_include_rules=False,
    )
    assert should_include_entity(
        "light.public",
        filter_config,
        {},
        excluded_targets,
        has_include_rules=False,
    )


async def test_group_target_membership_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test group targets refresh when their membership changes."""
    hass.states.async_set("group.downstairs", "on", {ATTR_ENTITY_ID: ["light.kitchen"]})
    action = Mock()
    unsubscribe = await async_track_target_entity_change(
        hass, {ATTR_ENTITY_ID: ["group.downstairs"]}, action
    )

    hass.states.async_set(
        "group.downstairs", "on", {ATTR_ENTITY_ID: ["light.living_room"]}
    )
    await hass.async_block_till_done()
    await async_fire_target_change_cooldown(hass, freezer)

    action.assert_called_once_with({"light.living_room"}, {"light.kitchen"})
    unsubscribe()


async def test_nested_group_target_membership_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test nested group targets refresh when membership changes."""
    hass.states.async_set("group.downstairs", "on", {ATTR_ENTITY_ID: ["group.lights"]})
    hass.states.async_set("group.lights", "on", {ATTR_ENTITY_ID: ["light.kitchen"]})
    action = Mock()
    unsubscribe = await async_track_target_entity_change(
        hass, {ATTR_ENTITY_ID: ["group.downstairs"]}, action
    )

    hass.states.async_set("group.lights", "on", {ATTR_ENTITY_ID: ["light.living_room"]})
    await hass.async_block_till_done()
    await async_fire_target_change_cooldown(hass, freezer)

    action.assert_called_once_with({"light.living_room"}, {"light.kitchen"})
    unsubscribe()


@pytest.mark.parametrize(
    ("entity_id", "attributes"),
    [
        ("light.kitchen", {}),
        ("group.downstairs", {ATTR_ENTITY_ID: ["light.kitchen"]}),
    ],
)
async def test_target_state_change_does_not_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    attributes: dict[str, list[str]],
) -> None:
    """Test state changes that preserve target membership do not refresh."""
    hass.states.async_set(entity_id, "on", attributes)
    action = Mock()
    unsubscribe = await async_track_target_entity_change(
        hass, {ATTR_ENTITY_ID: [entity_id]}, action
    )

    hass.states.async_set(entity_id, "off", attributes)
    await hass.async_block_till_done()
    await async_fire_target_change_cooldown(hass, freezer)

    action.assert_not_called()
    unsubscribe()


async def test_direct_device_target_topology_change(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test direct device targets refresh when a device becomes a child."""
    config_entry = MockConfigEntry(domain="demo")
    config_entry.add_to_hass(hass)
    parent = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("demo", "parent")},
    )
    future_child = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("demo", "child")},
    )
    child_entity = entity_registry.async_get_or_create(
        "light",
        "demo",
        "child",
        device_id=future_child.id,
    )
    action = Mock()
    unsubscribe = await async_track_target_entity_change(
        hass, {ATTR_DEVICE_ID: [parent.id]}, action
    )

    # Start a new setup session so the existing device can become a child.
    device_registry.async_config_entry_unloaded(config_entry.entry_id)
    device_registry.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("demo", "child")},
        parent_device_id=parent.id,
    )
    await hass.async_block_till_done()
    await async_fire_target_change_cooldown(hass, freezer)

    action.assert_called_once_with({child_entity.entity_id}, set())
    unsubscribe()


async def test_selective_refresh_and_unsubscribe(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    label_registry: lr.LabelRegistry,
) -> None:
    """Test selective target refresh and tracker unsubscription."""
    label = label_registry.async_create("HomeKit")
    registry_entry = entity_registry.async_get_or_create(
        "light", "demo", "target_tracker", suggested_object_id="target_tracker"
    )
    action = Mock()

    with patch(
        "homeassistant.helpers.target.async_extract_referenced_entity_ids",
        wraps=target_helper.async_extract_referenced_entity_ids,
    ) as mock_expand:
        unsubscribe = await async_track_target_entity_change(
            hass, {ATTR_LABEL_ID: [label.label_id]}, action
        )
        assert mock_expand.call_count == 1

        entity_registry.async_update_entity(registry_entry.entity_id, name="New name")
        await hass.async_block_till_done()
        await async_fire_target_change_cooldown(hass, freezer)
        assert mock_expand.call_count == 1
        action.assert_not_called()

        entity_registry.async_update_entity(
            registry_entry.entity_id, labels={label.label_id}
        )
        await hass.async_block_till_done()
        await async_fire_target_change_cooldown(hass, freezer)
        assert mock_expand.call_count == 2
        action.assert_called_once_with({registry_entry.entity_id}, set())

        entity_registry.async_update_entity(registry_entry.entity_id, labels=set())
        await hass.async_block_till_done()
        unsubscribe()
        await async_fire_target_change_cooldown(hass, freezer)
        assert mock_expand.call_count == 2
        action.assert_called_once()
