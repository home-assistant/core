"""Test alias template functions."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    floor_registry as fr,
)
from homeassistant.helpers.entity_registry import COMPUTED_NAME

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render_to_info


@pytest.mark.parametrize(
    "template",
    [
        "{{ aliases('sensor.fake') }}",
        "{{ 'sensor.fake' | aliases }}",
        "{{ aliases('unknown_slug') }}",
        "{{ 'unknown_slug' | aliases }}",
        "{{ aliases(42) }}",
        "{{ 42 | aliases }}",
    ],
)
async def test_aliases_unknown(hass: HomeAssistant, template: str) -> None:
    """Test aliases returns an empty list for unknown or invalid lookups."""
    info = render_to_info(hass, template)
    assert_result_info(info, [])
    assert info.rate_limit is None


async def test_aliases_entity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test aliases for an entity, sorted and with the sentinel filtered out."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=config_entry
    )
    entity_id = entity_entry.entity_id

    # No aliases yet
    info = render_to_info(hass, f"{{{{ aliases('{entity_id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{entity_id}' | aliases }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    # The COMPUTED_NAME sentinel is not a str and must be filtered out
    entity_registry.async_update_entity(
        entity_id, aliases=["Office Light Switch", COMPUTED_NAME, "Another Alias"]
    )
    info = render_to_info(hass, f"{{{{ aliases('{entity_id}') }}}}")
    assert_result_info(info, ["Another Alias", "Office Light Switch"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{entity_id}' | aliases }}}}")
    assert_result_info(info, ["Another Alias", "Office Light Switch"])
    assert info.rate_limit is None


async def test_aliases_entity_case_insensitive(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a mixed-case entity ID is normalized before the registry lookup."""
    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_entry = entity_registry.async_get_or_create(
        "light", "hue", "5678", config_entry=config_entry
    )
    entity_registry.async_update_entity(entity_entry.entity_id, aliases=["Kitchen"])

    upper_entity_id = entity_entry.entity_id.upper()
    info = render_to_info(hass, f"{{{{ aliases('{upper_entity_id}') }}}}")
    assert_result_info(info, ["Kitchen"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{upper_entity_id}' | aliases }}}}")
    assert_result_info(info, ["Kitchen"])
    assert info.rate_limit is None


async def test_aliases_area(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
) -> None:
    """Test aliases for an area by ID, returned sorted."""
    area = area_registry.async_create("Bedroom")

    info = render_to_info(hass, f"{{{{ aliases('{area.id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    area_registry.async_update(area.id, aliases={"Sleeping Room", "Bedchamber"})
    info = render_to_info(hass, f"{{{{ aliases('{area.id}') }}}}")
    assert_result_info(info, ["Bedchamber", "Sleeping Room"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{area.id}' | aliases }}}}")
    assert_result_info(info, ["Bedchamber", "Sleeping Room"])
    assert info.rate_limit is None


async def test_aliases_floor(
    hass: HomeAssistant,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test aliases for a floor by ID, returned sorted."""
    floor = floor_registry.async_create("Ground Floor")

    info = render_to_info(hass, f"{{{{ aliases('{floor.floor_id}') }}}}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    floor_registry.async_update(floor.floor_id, aliases={"Erdgeschoss", "Downstairs"})
    info = render_to_info(hass, f"{{{{ aliases('{floor.floor_id}') }}}}")
    assert_result_info(info, ["Downstairs", "Erdgeschoss"])
    assert info.rate_limit is None

    info = render_to_info(hass, f"{{{{ '{floor.floor_id}' | aliases }}}}")
    assert_result_info(info, ["Downstairs", "Erdgeschoss"])
    assert info.rate_limit is None


async def test_aliases_area_before_floor(
    hass: HomeAssistant,
    area_registry: ar.AreaRegistry,
    floor_registry: fr.FloorRegistry,
) -> None:
    """Test an ID that is both an area and a floor resolves to the area."""
    area = area_registry.async_create("Shared", aliases={"Area Alias"})
    floor = floor_registry.async_create("Shared", aliases={"Floor Alias"})
    # Both slugs collide; area must win the tiebreak
    assert area.id == floor.floor_id

    info = render_to_info(hass, f"{{{{ aliases('{area.id}') }}}}")
    assert_result_info(info, ["Area Alias"])
    assert info.rate_limit is None
