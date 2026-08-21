"""Tests for HomeKit target tracking."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.homekit.const import TARGET_CHANGE_RELOAD_COOLDOWN
from homeassistant.components.homekit.target import async_track_target_entity_change
from homeassistant.const import ATTR_ENTITY_ID, ATTR_LABEL_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    entity_registry as er,
    label_registry as lr,
    target as target_helper,
)

from tests.common import async_fire_time_changed


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
    freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

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
    freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    action.assert_called_once_with({"light.living_room"}, {"light.kitchen"})
    unsubscribe()


async def test_entity_target_state_change_does_not_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test state changes do not refresh non-group targets."""
    action = Mock()
    unsubscribe = await async_track_target_entity_change(
        hass, {ATTR_ENTITY_ID: ["light.kitchen"]}, action
    )

    hass.states.async_set("light.kitchen", "on")
    await hass.async_block_till_done()
    freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    action.assert_not_called()
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
        freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_expand.call_count == 1
        action.assert_not_called()

        entity_registry.async_update_entity(
            registry_entry.entity_id, labels={label.label_id}
        )
        await hass.async_block_till_done()
        freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_expand.call_count == 2
        action.assert_called_once_with({registry_entry.entity_id}, set())

        entity_registry.async_update_entity(registry_entry.entity_id, labels=set())
        await hass.async_block_till_done()
        unsubscribe()
        freezer.tick(TARGET_CHANGE_RELOAD_COOLDOWN)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert mock_expand.call_count == 2
        action.assert_called_once()
