"""Test service helpers."""

import pytest

from homeassistant.components.group import Group
from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_ENTITY_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    ENTITY_MATCH_NONE,
    STATE_OFF,
    STATE_ON,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
    target,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    RegistryEntryWithDefaults,
    mock_area_registry,
    mock_device_registry,
    mock_registry,
)


async def set_states_and_check_target_events(
    hass: HomeAssistant,
    events: list[target.TargetStateChangedData],
    state: str,
    entities_to_set_state: list[str],
    entities_to_assert_change: list[str],
) -> None:
    """Toggle the state entities and check for events."""
    for entity_id in entities_to_set_state:
        hass.states.async_set(entity_id, state)
    await hass.async_block_till_done()

    assert len(events) == len(entities_to_assert_change)
    entities_seen = set()
    for event in events:
        state_change_event = event.state_change_event
        entities_seen.add(state_change_event.data["entity_id"])
        assert state_change_event.data["new_state"].state == state
        assert event.targeted_entity_ids == set(entities_to_assert_change)
    assert entities_seen == set(entities_to_assert_change)
    events.clear()


@pytest.fixture
def registries_mock(hass: HomeAssistant) -> None:
    """Mock including floor and area info."""
    hass.states.async_set("light.Bowl", STATE_ON)
    hass.states.async_set("light.Ceiling", STATE_OFF)
    hass.states.async_set("light.Kitchen", STATE_OFF)

    area_in_floor = ar.AreaEntry(
        id="test-area",
        name="Test area",
        aliases={},
        floor_id="test-floor",
        icon=None,
        picture=None,
        temperature_entity_id=None,
        humidity_entity_id=None,
    )
    area_in_floor_a = ar.AreaEntry(
        id="area-a",
        name="Area A",
        aliases={},
        floor_id="floor-a",
        icon=None,
        picture=None,
        temperature_entity_id=None,
        humidity_entity_id=None,
    )
    area_with_labels = ar.AreaEntry(
        id="area-with-labels",
        name="Area with labels",
        aliases={},
        floor_id=None,
        icon=None,
        labels={"label_area"},
        picture=None,
        temperature_entity_id=None,
        humidity_entity_id=None,
    )
    mock_area_registry(
        hass,
        {
            area_in_floor.id: area_in_floor,
            area_in_floor_a.id: area_in_floor_a,
            area_with_labels.id: area_with_labels,
        },
    )

    device_in_area = dr.DeviceEntry(id="device-test-area", area_id="test-area")
    device_no_area = dr.DeviceEntry(id="device-no-area-id")
    device_diff_area = dr.DeviceEntry(id="device-diff-area", area_id="diff-area")
    device_area_a = dr.DeviceEntry(id="device-area-a-id", area_id="area-a")
    device_has_label1 = dr.DeviceEntry(id="device-has-label1-id", labels={"label1"})
    device_has_label2 = dr.DeviceEntry(id="device-has-label2-id", labels={"label2"})
    device_has_labels = dr.DeviceEntry(
        id="device-has-labels-id",
        labels={"label1", "label2"},
        area_id=area_with_labels.id,
    )

    mock_device_registry(
        hass,
        {
            device_in_area.id: device_in_area,
            device_no_area.id: device_no_area,
            device_diff_area.id: device_diff_area,
            device_area_a.id: device_area_a,
            device_has_label1.id: device_has_label1,
            device_has_label2.id: device_has_label2,
            device_has_labels.id: device_has_labels,
        },
    )

    entity_in_own_area = RegistryEntryWithDefaults(
        entity_id="light.in_own_area",
        unique_id="in-own-area-id",
        platform="test",
        area_id="own-area",
    )
    config_entity_in_own_area = RegistryEntryWithDefaults(
        entity_id="light.config_in_own_area",
        unique_id="config-in-own-area-id",
        platform="test",
        area_id="own-area",
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_in_own_area = RegistryEntryWithDefaults(
        entity_id="light.hidden_in_own_area",
        unique_id="hidden-in-own-area-id",
        platform="test",
        area_id="own-area",
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_in_area = RegistryEntryWithDefaults(
        entity_id="light.in_area",
        unique_id="in-area-id",
        platform="test",
        device_id=device_in_area.id,
    )
    config_entity_in_area = RegistryEntryWithDefaults(
        entity_id="light.config_in_area",
        unique_id="config-in-area-id",
        platform="test",
        device_id=device_in_area.id,
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_in_area = RegistryEntryWithDefaults(
        entity_id="light.hidden_in_area",
        unique_id="hidden-in-area-id",
        platform="test",
        device_id=device_in_area.id,
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_in_other_area = RegistryEntryWithDefaults(
        entity_id="light.in_other_area",
        unique_id="in-area-a-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="other-area",
    )
    entity_assigned_to_area = RegistryEntryWithDefaults(
        entity_id="light.assigned_to_area",
        unique_id="assigned-area-id",
        platform="test",
        device_id=device_in_area.id,
        area_id="test-area",
    )
    entity_no_area = RegistryEntryWithDefaults(
        entity_id="light.no_area",
        unique_id="no-area-id",
        platform="test",
        device_id=device_no_area.id,
    )
    config_entity_no_area = RegistryEntryWithDefaults(
        entity_id="light.config_no_area",
        unique_id="config-no-area-id",
        platform="test",
        device_id=device_no_area.id,
        entity_category=EntityCategory.CONFIG,
    )
    hidden_entity_no_area = RegistryEntryWithDefaults(
        entity_id="light.hidden_no_area",
        unique_id="hidden-no-area-id",
        platform="test",
        device_id=device_no_area.id,
        hidden_by=er.RegistryEntryHider.USER,
    )
    entity_diff_area = RegistryEntryWithDefaults(
        entity_id="light.diff_area",
        unique_id="diff-area-id",
        platform="test",
        device_id=device_diff_area.id,
    )
    entity_in_area_a = RegistryEntryWithDefaults(
        entity_id="light.in_area_a",
        unique_id="in-area-a-id",
        platform="test",
        device_id=device_area_a.id,
        area_id="area-a",
    )
    entity_in_area_b = RegistryEntryWithDefaults(
        entity_id="light.in_area_b",
        unique_id="in-area-b-id",
        platform="test",
        device_id=device_area_a.id,
        area_id="area-b",
    )
    entity_with_my_label = RegistryEntryWithDefaults(
        entity_id="light.with_my_label",
        unique_id="with_my_label",
        platform="test",
        labels={"my-label"},
    )
    hidden_entity_with_my_label = RegistryEntryWithDefaults(
        entity_id="light.hidden_with_my_label",
        unique_id="hidden_with_my_label",
        platform="test",
        labels={"my-label"},
        hidden_by=er.RegistryEntryHider.USER,
    )
    config_entity_with_my_label = RegistryEntryWithDefaults(
        entity_id="light.config_with_my_label",
        unique_id="config_with_my_label",
        platform="test",
        labels={"my-label"},
        entity_category=EntityCategory.CONFIG,
    )
    entity_with_label1_from_device = RegistryEntryWithDefaults(
        entity_id="light.with_label1_from_device",
        unique_id="with_label1_from_device",
        platform="test",
        device_id=device_has_label1.id,
    )
    entity_with_label1_from_device_and_different_area = RegistryEntryWithDefaults(
        entity_id="light.with_label1_from_device_diff_area",
        unique_id="with_label1_from_device_diff_area",
        platform="test",
        device_id=device_has_label1.id,
        area_id=area_in_floor_a.id,
    )
    entity_with_label1_and_label2_from_device = RegistryEntryWithDefaults(
        entity_id="light.with_label1_and_label2_from_device",
        unique_id="with_label1_and_label2_from_device",
        platform="test",
        labels={"label1"},
        device_id=device_has_label2.id,
    )
    entity_with_labels_from_device = RegistryEntryWithDefaults(
        entity_id="light.with_labels_from_device",
        unique_id="with_labels_from_device",
        platform="test",
        device_id=device_has_labels.id,
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
            config_entity_with_my_label.entity_id: config_entity_with_my_label,
            entity_with_label1_and_label2_from_device.entity_id: entity_with_label1_and_label2_from_device,
            entity_with_label1_from_device.entity_id: entity_with_label1_from_device,
            entity_with_label1_from_device_and_different_area.entity_id: entity_with_label1_from_device_and_different_area,
            entity_with_labels_from_device.entity_id: entity_with_labels_from_device,
            entity_with_my_label.entity_id: entity_with_my_label,
            hidden_entity_with_my_label.entity_id: hidden_entity_with_my_label,
        },
    )


@pytest.mark.parametrize(
    ("selector_config", "expand_group", "expected_selected"),
    [
        (
            {
                ATTR_ENTITY_ID: ENTITY_MATCH_NONE,
                ATTR_AREA_ID: ENTITY_MATCH_NONE,
                ATTR_FLOOR_ID: ENTITY_MATCH_NONE,
                ATTR_LABEL_ID: ENTITY_MATCH_NONE,
            },
            False,
            target.SelectedEntities(),
        ),
        (
            {ATTR_ENTITY_ID: "light.bowl"},
            False,
            target.SelectedEntities(referenced={"light.bowl"}),
        ),
        (
            {ATTR_ENTITY_ID: "group.test"},
            True,
            target.SelectedEntities(referenced={"light.ceiling", "light.kitchen"}),
        ),
        (
            {ATTR_ENTITY_ID: "group.test"},
            False,
            target.SelectedEntities(referenced={"group.test"}),
        ),
        (
            {ATTR_AREA_ID: "own-area"},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.in_own_area"},
                referenced_areas={"own-area"},
                missing_areas={"own-area"},
            ),
        ),
        (
            {ATTR_AREA_ID: "test-area"},
            False,
            target.SelectedEntities(
                indirectly_referenced={
                    "light.in_area",
                    "light.assigned_to_area",
                },
                referenced_areas={"test-area"},
                referenced_devices={"device-test-area"},
            ),
        ),
        (
            {ATTR_AREA_ID: ["test-area", "diff-area"]},
            False,
            target.SelectedEntities(
                indirectly_referenced={
                    "light.in_area",
                    "light.diff_area",
                    "light.assigned_to_area",
                },
                referenced_areas={"test-area", "diff-area"},
                referenced_devices={"device-diff-area", "device-test-area"},
                missing_areas={"diff-area"},
            ),
        ),
        (
            {ATTR_DEVICE_ID: "device-no-area-id"},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.no_area"},
                referenced_devices={"device-no-area-id"},
            ),
        ),
        (
            {ATTR_DEVICE_ID: "device-area-a-id"},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.in_area_a", "light.in_area_b"},
                referenced_devices={"device-area-a-id"},
            ),
        ),
        (
            {ATTR_FLOOR_ID: "test-floor"},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.in_area", "light.assigned_to_area"},
                referenced_devices={"device-test-area"},
                referenced_areas={"test-area"},
                missing_floors={"test-floor"},
            ),
        ),
        (
            {ATTR_FLOOR_ID: ["test-floor", "floor-a"]},
            False,
            target.SelectedEntities(
                indirectly_referenced={
                    "light.in_area",
                    "light.assigned_to_area",
                    "light.in_area_a",
                    "light.with_label1_from_device_diff_area",
                },
                referenced_devices={"device-area-a-id", "device-test-area"},
                referenced_areas={"area-a", "test-area"},
                missing_floors={"floor-a", "test-floor"},
            ),
        ),
        (
            {ATTR_LABEL_ID: "my-label"},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.with_my_label"},
                missing_labels={"my-label"},
            ),
        ),
        (
            {ATTR_LABEL_ID: "label1"},
            False,
            target.SelectedEntities(
                indirectly_referenced={
                    "light.with_label1_from_device",
                    "light.with_label1_from_device_diff_area",
                    "light.with_labels_from_device",
                    "light.with_label1_and_label2_from_device",
                },
                referenced_devices={"device-has-label1-id", "device-has-labels-id"},
                missing_labels={"label1"},
            ),
        ),
        (
            {ATTR_LABEL_ID: ["label2"]},
            False,
            target.SelectedEntities(
                indirectly_referenced={
                    "light.with_labels_from_device",
                    "light.with_label1_and_label2_from_device",
                },
                referenced_devices={"device-has-label2-id", "device-has-labels-id"},
                missing_labels={"label2"},
            ),
        ),
        (
            {ATTR_LABEL_ID: ["label_area"]},
            False,
            target.SelectedEntities(
                indirectly_referenced={"light.with_labels_from_device"},
                referenced_devices={"device-has-labels-id"},
                referenced_areas={"area-with-labels"},
                missing_labels={"label_area"},
            ),
        ),
    ],
)
@pytest.mark.usefixtures("registries_mock")
async def test_extract_referenced_entity_ids(
    hass: HomeAssistant,
    selector_config: ConfigType,
    expand_group: bool,
    expected_selected: target.SelectedEntities,
) -> None:
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

    target_data = target.TargetSelectorData(selector_config)
    assert (
        target.async_extract_referenced_entity_ids(
            hass, target_data, expand_group=expand_group
        )
        == expected_selected
    )


async def test_async_track_target_selector_state_change_event_empty_selector(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test async_track_target_selector_state_change_event with empty selector."""

    @callback
    def state_change_callback(event):
        """Handle state change events."""

    with pytest.raises(HomeAssistantError) as excinfo:
        target.async_track_target_selector_state_change_event(
            hass, {}, state_change_callback
        )
    assert str(excinfo.value) == (
        "Target selector {} does not have any selectors defined"
    )


async def test_async_track_target_selector_state_change_event(
    hass: HomeAssistant,
) -> None:
    """Test async_track_target_selector_state_change_event with multiple targets."""
    events: list[target.TargetStateChangedData] = []

    @callback
    def state_change_callback(event: target.TargetStateChangedData):
        """Handle state change events."""
        events.append(event)

    last_state = STATE_OFF

    async def set_states_and_check_events(
        entities_to_set_state: list[str], entities_to_assert_change: list[str]
    ) -> None:
        """Toggle the state entities and check for events."""
        nonlocal last_state
        last_state = STATE_ON if last_state == STATE_OFF else STATE_OFF
        await set_states_and_check_target_events(
            hass, events, last_state, entities_to_set_state, entities_to_assert_change
        )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "device_1")},
    )

    untargeted_device_entry = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test", "area_device")},
    )

    entity_reg = er.async_get(hass)
    device_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="device_light",
        device_id=device_entry.id,
    ).entity_id

    untargeted_device_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="area_device_light",
        device_id=untargeted_device_entry.id,
    ).entity_id

    untargeted_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="untargeted_light",
    ).entity_id

    targeted_entity = "light.test_light"

    targeted_entities = [targeted_entity, device_entity]
    await set_states_and_check_events(targeted_entities, [])

    label = lr.async_get(hass).async_create("Test Label").name
    area = ar.async_get(hass).async_create("Test Area").id
    floor = fr.async_get(hass).async_create("Test Floor").floor_id

    selector_config = {
        ATTR_ENTITY_ID: targeted_entity,
        ATTR_DEVICE_ID: device_entry.id,
        ATTR_AREA_ID: area,
        ATTR_FLOOR_ID: floor,
        ATTR_LABEL_ID: label,
    }
    unsub = target.async_track_target_selector_state_change_event(
        hass, selector_config, state_change_callback
    )

    # Test directly targeted entity and device
    await set_states_and_check_events(targeted_entities, targeted_entities)

    # Add new entity to the targeted device -> should trigger on state change
    device_entity_2 = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="device_light_2",
        device_id=device_entry.id,
    ).entity_id

    targeted_entities = [targeted_entity, device_entity, device_entity_2]
    await set_states_and_check_events(targeted_entities, targeted_entities)

    # Test untargeted entity -> should not trigger
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], targeted_entities
    )

    # Add label to untargeted entity -> should trigger now
    entity_reg.async_update_entity(untargeted_entity, labels={label})
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], [*targeted_entities, untargeted_entity]
    )

    # Remove label from untargeted entity -> should not trigger anymore
    entity_reg.async_update_entity(untargeted_entity, labels={})
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], targeted_entities
    )

    # Add area to untargeted entity -> should trigger now
    entity_reg.async_update_entity(untargeted_entity, area_id=area)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], [*targeted_entities, untargeted_entity]
    )

    # Remove area from untargeted entity -> should not trigger anymore
    entity_reg.async_update_entity(untargeted_entity, area_id=None)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], targeted_entities
    )

    # Add area to untargeted device -> should trigger on state change
    device_reg.async_update_device(untargeted_device_entry.id, area_id=area)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_device_entity],
        [*targeted_entities, untargeted_device_entity],
    )

    # Remove area from untargeted device -> should not trigger anymore
    device_reg.async_update_device(untargeted_device_entry.id, area_id=None)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_device_entity], targeted_entities
    )

    # Set the untargeted area on the untargeted entity -> should not trigger
    untracked_area = ar.async_get(hass).async_create("Untargeted Area").id
    entity_reg.async_update_entity(untargeted_entity, area_id=untracked_area)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], targeted_entities
    )

    # Set targeted floor on the untargeted area -> should trigger now
    ar.async_get(hass).async_update(untracked_area, floor_id=floor)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity],
        [*targeted_entities, untargeted_entity],
    )

    # Remove untargeted area from targeted floor -> should not trigger anymore
    ar.async_get(hass).async_update(untracked_area, floor_id=None)
    await set_states_and_check_events(
        [*targeted_entities, untargeted_entity], targeted_entities
    )

    # After unsubscribing, changes should not trigger
    unsub()
    await set_states_and_check_events(targeted_entities, [])


async def test_async_track_target_selector_state_change_event_filter(
    hass: HomeAssistant,
) -> None:
    """Test async_track_target_selector_state_change_event with entity filter."""
    events: list[target.TargetStateChangedData] = []

    filtered_entity = ""

    @callback
    def entity_filter(entity_ids: set[str]) -> set[str]:
        return {entity_id for entity_id in entity_ids if entity_id != filtered_entity}

    @callback
    def state_change_callback(event: target.TargetStateChangedData):
        """Handle state change events."""
        events.append(event)

    last_state = STATE_OFF

    async def set_states_and_check_events(
        entities_to_set_state: list[str], entities_to_assert_change: list[str]
    ) -> None:
        """Toggle the state entities and check for events."""
        nonlocal last_state
        last_state = STATE_ON if last_state == STATE_OFF else STATE_OFF
        await set_states_and_check_target_events(
            hass, events, last_state, entities_to_set_state, entities_to_assert_change
        )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    entity_reg = er.async_get(hass)

    label = lr.async_get(hass).async_create("Test Label").name
    label_entity = entity_reg.async_get_or_create(
        domain="light",
        platform="test",
        unique_id="label_light",
    ).entity_id
    entity_reg.async_update_entity(label_entity, labels={label})

    targeted_entity = "light.test_light"

    targeted_entities = [targeted_entity, label_entity]
    await set_states_and_check_events(targeted_entities, [])

    selector_config = {
        ATTR_ENTITY_ID: targeted_entity,
        ATTR_LABEL_ID: label,
    }
    unsub = target.async_track_target_selector_state_change_event(
        hass, selector_config, state_change_callback, entity_filter
    )

    await set_states_and_check_events(
        targeted_entities, [targeted_entity, label_entity]
    )

    filtered_entity = targeted_entity
    # Fire an event so that the targeted entities are re-evaluated
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {
            "action": "update",
            "entity_id": "light.other",
            "changes": {},
        },
    )
    await set_states_and_check_events([targeted_entity, label_entity], [label_entity])

    filtered_entity = label_entity
    # Fire an event so that the targeted entities are re-evaluated
    hass.bus.async_fire(
        er.EVENT_ENTITY_REGISTRY_UPDATED,
        {
            "action": "update",
            "entity_id": "light.other",
            "changes": {},
        },
    )
    await set_states_and_check_events(
        [targeted_entity, label_entity], [targeted_entity]
    )

    unsub()
