"""Test service helpers."""

import pytest

# TODO(abmantis): is this import needed?
# To prevent circular import when running just this file
import homeassistant.components  # noqa: F401
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
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    target,
)
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from tests.common import (
    RegistryEntryWithDefaults,
    mock_area_registry,
    mock_device_registry,
    mock_registry,
)


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
