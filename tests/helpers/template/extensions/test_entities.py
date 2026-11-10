"""Test entity functions for Home Assistant templates."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, MockEntity, MockEntityPlatform

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.group import GenericGroup

from tests.helpers.template.helpers import render


def test_entity_name(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test entity_name method."""
    assert render(hass, "{{ entity_name('sensor.fake') }}") is None

    entry = entity_registry.async_get_or_create(
        "sensor", "test", "unique_1", original_name="Registry Sensor"
    )
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "Registry Sensor"
    )
    assert render(hass, f"{{{{ '{entry.entity_id}' | entity_name }}}}") == (
        "Registry Sensor"
    )

    entity_registry.async_update_entity(entry.entity_id, name="My Custom Sensor")
    assert render(hass, f"{{{{ entity_name('{entry.entity_id}') }}}}") == (
        "My Custom Sensor"
    )

    # Falls back to state for entities not in the registry
    hass.states.async_set(
        "light.no_unique_id", "on", {"friendly_name": "No Unique ID Light"}
    )
    assert render(hass, "{{ entity_name('light.no_unique_id') }}") == (
        "No Unique ID Light"
    )

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        name="My Device",
    )
    entry2 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_2",
        config_entry=config_entry,
        device_id=device_entry.id,
        has_entity_name=True,
        original_name="Temperature",
    )
    assert render(hass, f"{{{{ entity_name('{entry2.entity_id}') }}}}") == (
        "Temperature"
    )
    assert (
        render(hass, f"{{{{ entity_name('{entry2.entity_id}', fallback=True) }}}}")
        == "Temperature"
    )

    # The main entity of a device has no name of its own
    entry3 = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "unique_3",
        config_entry=config_entry,
        device_id=device_entry.id,
        has_entity_name=True,
    )
    assert render(hass, f"{{{{ entity_name('{entry3.entity_id}') }}}}") == ""
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "My Device"
    )
    assert (
        render(hass, f"{{{{ '{entry3.entity_id}' | entity_name(fallback=True) }}}}")
        == "My Device"
    )

    device_registry.async_update_device(device_entry.id, name_by_user="User Device")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "User Device"
    )

    entity_registry.async_update_entity(entry3.entity_id, name="")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "User Device"
    )

    entity_registry.async_update_entity(entry3.entity_id, name="Own Name")
    assert (
        render(hass, f"{{{{ entity_name('{entry3.entity_id}', fallback=True) }}}}")
        == "Own Name"
    )


def test_is_hidden_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test is_hidden_entity method."""
    hidden_entity = entity_registry.async_get_or_create(
        "sensor", "mock", "hidden", hidden_by=er.RegistryEntryHider.USER
    )
    visible_entity = entity_registry.async_get_or_create("sensor", "mock", "visible")
    assert render(hass, f"{{{{ is_hidden_entity('{hidden_entity.entity_id}') }}}}")

    assert not render(hass, f"{{{{ is_hidden_entity('{visible_entity.entity_id}') }}}}")

    assert not render(
        hass,
        f"{{{{ ['{visible_entity.entity_id}']"
        f" | select('is_hidden_entity') | first }}}}",
    )


async def test_resolve_target(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test resolving direct and indirect entity targets."""
    area = area_registry.async_get_or_create("Test area")
    direct_entity = entity_registry.async_get_or_create(
        "sensor", "test", "direct"
    ).entity_id
    indirect_entity = entity_registry.async_get_or_create(
        "sensor", "test", "indirect"
    ).entity_id
    entity_registry.async_update_entity(indirect_entity, area_id=area.id)
    target = {"entity_id": direct_entity, "area_id": area.id}

    assert set(render(hass, "{{ resolve_target(target) }}", {"target": target})) == {
        direct_entity,
        indirect_entity,
    }
    assert set(render(hass, "{{ target | resolve_target }}", {"target": target})) == {
        direct_entity,
        indirect_entity,
    }


async def test_resolve_target_entity_ids(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test resolving comma-separated entity IDs and registry IDs."""
    first_entity = entity_registry.async_get_or_create(
        "sensor", "test", "first"
    ).entity_id
    second_entry = entity_registry.async_get_or_create("sensor", "test", "second")

    assert set(
        render(
            hass,
            "{{ resolve_target(target) }}",
            {"target": {"entity_id": f"{first_entity}, {second_entry.entity_id}"}},
        )
    ) == {first_entity, second_entry.entity_id}
    assert set(
        render(
            hass,
            "{{ resolve_target(target) }}",
            {"target": {"entity_id": second_entry.id}},
        )
    ) == {second_entry.entity_id}


@pytest.mark.parametrize("target", [None, [], "sensor.test", 123, {}])
def test_resolve_target_empty_or_invalid(hass: HomeAssistant, target: object) -> None:
    """Test resolving an empty or invalid target."""
    assert render(hass, "{{ resolve_target(target) }}", {"target": target}) == []


@pytest.mark.parametrize(
    ("expand_group", "expected"),
    [
        (True, {"light.group_member"}),
        (False, {"light.test_group"}),
    ],
)
async def test_resolve_target_expand_group(
    hass: HomeAssistant, expand_group: bool, expected: set[str]
) -> None:
    """Test expanding groups can be controlled."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")
    group = MockEntity(entity_id="light.test_group", unique_id="group")
    group.group = GenericGroup(group, ["light.group_member"])
    await platform.async_add_entities([group])
    await hass.async_block_till_done()

    assert (
        set(
            render(
                hass,
                "{{ resolve_target(target, expand_group=expand_group) }}",
                {
                    "target": {"entity_id": group.entity_id},
                    "expand_group": expand_group,
                },
            )
        )
        == expected
    )


@pytest.mark.parametrize(
    ("expand_group", "expected"),
    [
        (True, {"light.other"}),
        (False, {"light.group_member", "light.other"}),
    ],
)
async def test_resolve_target_all(
    hass: HomeAssistant, expand_group: bool, expected: set[str]
) -> None:
    """Test resolving all entities and applying group exclusions."""
    platform = MockEntityPlatform(hass, domain="light", platform_name="test")
    group = MockEntity(entity_id="light.test_group", unique_id="group")
    group.group = GenericGroup(group, ["light.group_member"])
    await platform.async_add_entities([group])
    await hass.async_block_till_done()
    hass.states.async_set("light.group_member", "on")
    hass.states.async_set("light.other", "on")

    assert (
        set(
            render(
                hass,
                "{{ resolve_target(target, expand_group=expand_group) }}",
                {
                    "target": {
                        "entity_id": "all",
                        "exclude": {"entity_id": group.entity_id},
                    },
                    "expand_group": expand_group,
                },
            )
        )
        == expected
    )


async def test_resolve_target_primary_entities_only(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test primary_entities_only controls config entity inclusion."""
    area = area_registry.async_get_or_create("Test area")
    primary_entity = entity_registry.async_get_or_create(
        "sensor", "test", "primary"
    ).entity_id
    config_entity = entity_registry.async_get_or_create(
        "sensor",
        "test",
        "config",
        entity_category=EntityCategory.CONFIG,
    ).entity_id
    entity_registry.async_update_entity(primary_entity, area_id=area.id)
    entity_registry.async_update_entity(config_entity, area_id=area.id)
    target = {"area_id": area.id}

    assert set(
        render(
            hass,
            "{{ resolve_target(target, primary_entities_only=True) }}",
            {"target": target},
        )
    ) == {primary_entity}
    assert set(
        render(
            hass,
            "{{ resolve_target(target, primary_entities_only=False) }}",
            {"target": target},
        )
    ) == {primary_entity, config_entity}
