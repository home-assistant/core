"""Test state functions for Home Assistant templates."""

from __future__ import annotations

from collections.abc import Iterable
from unittest.mock import patch

import pytest

from homeassistant.components import group
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    UnitOfArea,
    UnitOfLength,
    UnitOfMass,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import entity_registry as er, template, translation
from homeassistant.helpers.template.render_info import (
    ALL_STATES_RATE_LIMIT,
    DOMAIN_STATES_RATE_LIMIT,
)
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import UnitSystem

from tests.common import MockConfigEntry
from tests.helpers.template.helpers import assert_result_info, render, render_to_info


def _set_up_units(hass: HomeAssistant) -> None:
    """Set up the tests."""
    hass.config.units = UnitSystem(
        "custom",
        accumulated_precipitation=UnitOfPrecipitationDepth.MILLIMETERS,
        area=UnitOfArea.SQUARE_METERS,
        conversions={},
        length=UnitOfLength.METERS,
        mass=UnitOfMass.GRAMS,
        pressure=UnitOfPressure.PA,
        temperature=UnitOfTemperature.CELSIUS,
        volume=UnitOfVolume.LITERS,
        wind_speed=UnitOfSpeed.KILOMETERS_PER_HOUR,
    )


def test_referring_states_by_entity_id(hass: HomeAssistant) -> None:
    """Test referring states by entity id."""
    hass.states.async_set("test.object", "happy")
    assert render(hass, "{{ states.test.object.state }}") == "happy"

    assert render(hass, '{{ states["test.object"].state }}') == "happy"

    assert render(hass, '{{ states("test.object") }}') == "happy"


def test_iterating_all_states(hass: HomeAssistant) -> None:
    """Test iterating all states."""
    tmpl_str = "{% for state in states | sort(attribute='entity_id') %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", all_states=True)
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "10happy", entities=[], all_states=True)


def test_iterating_all_states_unavailable(hass: HomeAssistant) -> None:
    """Test iterating all states unavailable."""
    hass.states.async_set("test.object", "on")

    tmpl_str = (
        "{{"
        "  states"
        "  | selectattr('state', 'in', ['unavailable', 'unknown', 'none'])"
        "  | list"
        "  | count"
        "}}"
    )

    info = render_to_info(hass, tmpl_str)

    assert info.all_states is True
    assert info.rate_limit == ALL_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "unknown")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, 1, entities=[], all_states=True)


def test_iterating_domain_states(hass: HomeAssistant) -> None:
    """Test iterating domain states."""
    tmpl_str = "{% for state in states.sensor %}{{ state.state }}{% endfor %}"

    info = render_to_info(hass, tmpl_str)
    assert_result_info(info, "", domains=["sensor"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    hass.states.async_set("test.object", "happy")
    hass.states.async_set("sensor.back_door", "open")
    hass.states.async_set("sensor.temperature", 10)

    info = render_to_info(hass, tmpl_str)
    assert_result_info(
        info,
        "open10",
        entities=[],
        domains=["sensor"],
    )


def test_if_state_exists(hass: HomeAssistant) -> None:
    """Test if state exists works."""
    hass.states.async_set("test.object", "available")

    result = render(
        hass, "{% if states.test.object %}exists{% else %}not exists{% endif %}"
    )
    assert result == "exists"


def test_is_state(hass: HomeAssistant) -> None:
    """Test is_state method."""
    hass.states.async_set("test.object", "available")

    result = render(
        hass, '{% if is_state("test.object", "available") %}yes{% else %}no{% endif %}'
    )
    assert result == "yes"

    result = render(hass, """{{ is_state("test.noobject", "available") }}""")
    assert result is False

    result = render(
        hass,
        '{% if "test.object" is is_state("available") %}yes{% else %}no{% endif %}',
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | select("is_state", "available") | first | default }}""",
    )
    assert result == "test.object"

    result = render(hass, '{{ is_state("test.object", ["on", "off", "available"]) }}')
    assert result is True


def test_is_state_attr(hass: HomeAssistant) -> None:
    """Test is_state_attr method."""
    hass.states.async_set("test.object", "available", {"mode": "on", "exists": None})

    result = render(
        hass,
        """{% if is_state_attr("test.object", "mode", "on") %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ is_state_attr("test.noobject", "mode", "on") }}""")
    assert result is False

    result = render(
        hass,
        """{% if "test.object" is is_state_attr("mode", "on") %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | select("is_state_attr", "mode", "on") | first | default }}""",
    )
    assert result == "test.object"

    result = render(
        hass,
        """{% if is_state_attr("test.object", "exists", None) %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{% if is_state_attr("test.object", "noexist", None) %}yes{% else %}no{% endif %}""",
    )
    assert result == "no"


def test_state_attr(hass: HomeAssistant) -> None:
    """Test state_attr method."""
    hass.states.async_set(
        "test.object", "available", {"effect": "action", "mode": "on"}
    )

    result = render(
        hass,
        """{% if state_attr("test.object", "mode") == "on" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ state_attr("test.noobject", "mode") == None }}""")
    assert result is True

    result = render(
        hass,
        """{% if "test.object" | state_attr("mode") == "on" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(
        hass,
        """{{ ['test.object'] | map("state_attr", "effect") | first | default }}""",
    )
    assert result == "action"


def test_states_function(hass: HomeAssistant) -> None:
    """Test using states as a function."""
    hass.states.async_set("test.object", "available")

    result = render(hass, '{{ states("test.object") }}')
    assert result == "available"

    result = render(hass, '{{ states("test.object2") }}')
    assert result == "unknown"

    result = render(
        hass,
        """{% if "test.object" | states == "available" %}yes{% else %}no{% endif %}""",
    )
    assert result == "yes"

    result = render(hass, """{{ ['test.object'] | map("states") | first | default }}""")
    assert result == "available"


async def test_state_translated(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test state_translated method."""
    assert await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": {
                "platform": "group",
                "name": "Grouped",
                "entities": ["binary_sensor.first", "binary_sensor.second"],
            }
        },
    )
    await hass.async_block_till_done()
    await translation._async_get_translations_cache(hass).async_load("en", set())

    hass.states.async_set("switch.without_translations", "on", attributes={})
    hass.states.async_set("binary_sensor.without_device_class", "on", attributes={})
    hass.states.async_set(
        "binary_sensor.with_device_class", "on", attributes={"device_class": "motion"}
    )
    hass.states.async_set(
        "binary_sensor.with_unknown_device_class",
        "on",
        attributes={"device_class": "unknown_class"},
    )
    hass.states.async_set(
        "some_domain.with_device_class_1",
        "off",
        attributes={"device_class": "some_device_class"},
    )
    hass.states.async_set(
        "some_domain.with_device_class_2",
        "foo",
        attributes={"device_class": "some_device_class"},
    )
    hass.states.async_set("domain.is_unavailable", "unavailable", attributes={})
    hass.states.async_set("domain.is_unknown", "unknown", attributes={})

    config_entry = MockConfigEntry(domain="light")
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "light",
        "hue",
        "5678",
        config_entry=config_entry,
        translation_key="translation_key",
    )
    hass.states.async_set("light.hue_5678", "on", attributes={})

    result = render(hass, '{{ state_translated("switch.without_translations") }}')
    assert result == "on"

    result = render(
        hass, '{{ state_translated("binary_sensor.without_device_class") }}'
    )
    assert result == "On"

    result = render(hass, '{{ state_translated("binary_sensor.with_device_class") }}')
    assert result == "Detected"

    result = render(
        hass, '{{ state_translated("binary_sensor.with_unknown_device_class") }}'
    )
    assert result == "On"

    with pytest.raises(TemplateError):
        render(hass, '{{ state_translated("contextfunction") }}')

    result = render(hass, '{{ state_translated("switch.invalid") }}')
    assert result == "unknown"

    with pytest.raises(TemplateError):
        render(hass, '{{ state_translated("-invalid") }}')

    def mock_get_cached_translations(
        _hass: HomeAssistant,
        _language: str,
        category: str,
        _integrations: Iterable[str] | None = None,
    ):
        if category == "entity":
            return {
                "component.hue.entity.light.translation_key.state.on": "state_is_on",
            }
        return {}

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        side_effect=mock_get_cached_translations,
    ):
        result = render(hass, '{{ state_translated("light.hue_5678") }}')
        assert result == "state_is_on"

    result = render(hass, '{{ state_translated("domain.is_unavailable") }}')
    assert result == "unavailable"

    result = render(hass, '{{ state_translated("domain.is_unknown") }}')
    assert result == "unknown"


async def test_state_attr_translated(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test state_attr_translated method."""
    await translation._async_get_translations_cache(hass).async_load("en", set())

    hass.states.async_set(
        "climate.living_room",
        "heat",
        attributes={"fan_mode": "auto", "hvac_action": "heating"},
    )
    hass.states.async_set(
        "switch.test",
        "on",
        attributes={"some_attr": "some_value", "numeric_attr": 42, "bool_attr": True},
    )

    result = render(
        hass,
        '{{ state_attr_translated("switch.test", "some_attr") }}',
    )
    assert result == "some_value"

    # Non-string attributes should be returned as-is without type conversion
    result = render(
        hass,
        '{{ state_attr_translated("switch.test", "numeric_attr") }}',
    )
    assert result == 42
    assert isinstance(result, int)

    result = render(
        hass,
        '{{ state_attr_translated("switch.test", "bool_attr") }}',
    )
    assert result is True

    result = render(
        hass,
        '{{ state_attr_translated("climate.non_existent", "fan_mode") }}',
    )
    assert result is None

    with pytest.raises(TemplateError):
        render(hass, '{{ state_attr_translated("-invalid", "fan_mode") }}')

    result = render(
        hass,
        '{{ state_attr_translated("climate.living_room", "non_existent") }}',
    )
    assert result is None


@pytest.mark.parametrize(
    (
        "entity_id",
        "attribute",
        "translations",
        "expected_result",
    ),
    [
        (
            "climate.test_platform_5678",
            "fan_mode",
            {
                "component.test_platform.entity.climate.my_climate.state_attributes.fan_mode.state.auto": "Platform Automatic",
            },
            "Platform Automatic",
        ),
        (
            "climate.living_room",
            "fan_mode",
            {
                "component.climate.entity_component._.state_attributes.fan_mode.state.auto": "Automatic",
            },
            "Automatic",
        ),
        (
            "climate.living_room",
            "hvac_action",
            {
                "component.climate.entity_component._.state_attributes.hvac_action.state.heating": "Heating",
            },
            "Heating",
        ),
    ],
)
async def test_state_attr_translated_translation_lookups(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    attribute: str,
    translations: dict[str, str],
    expected_result: str,
) -> None:
    """Test state_attr_translated translation lookups."""
    await translation._async_get_translations_cache(hass).async_load("en", set())

    hass.states.async_set(
        "climate.living_room",
        "heat",
        attributes={"fan_mode": "auto", "hvac_action": "heating"},
    )

    config_entry = MockConfigEntry(domain="climate")
    config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "climate",
        "test_platform",
        "5678",
        config_entry=config_entry,
        translation_key="my_climate",
    )
    hass.states.async_set(
        "climate.test_platform_5678",
        "heat",
        attributes={"fan_mode": "auto"},
    )

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value=translations,
    ):
        result = render(
            hass,
            f'{{{{ state_attr_translated("{entity_id}", "{attribute}") }}}}',
        )
        assert result == expected_result


def test_has_value(hass: HomeAssistant) -> None:
    """Test has_value method."""
    hass.states.async_set("test.value1", 1)
    hass.states.async_set("test.unavailable", STATE_UNAVAILABLE)

    result = render(hass, """{{ has_value("test.value1") }}""")
    assert result is True

    result = render(hass, """{{ has_value("test.unavailable") }}""")
    assert result is False

    result = render(hass, """{{ has_value("test.unknown") }}""")
    assert result is False

    result = render(
        hass, """{% if "test.value1" is has_value %}yes{% else %}no{% endif %}"""
    )
    assert result == "yes"


def test_distance_function_with_1_state(hass: HomeAssistant) -> None:
    """Test distance function with 1 state."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )

    result = render(hass, "{{ distance(states.test.object) | round }}")
    assert result == 187


def test_distance_function_with_2_states(hass: HomeAssistant) -> None:
    """Test distance function with 2 states."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, "{{ distance(states.test.object, states.test.object_2) | round }}"
    )
    assert result == 187


def test_distance_function_with_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 coord."""
    _set_up_units(hass)

    result = render(hass, '{{ distance("32.87336", "-117.22943") | round }}')
    assert result == 187


def test_distance_function_with_2_coords(hass: HomeAssistant) -> None:
    """Test distance function with 2 coords."""
    _set_up_units(hass)
    tpl = f'{{{{ distance("32.87336", "-117.22943", {hass.config.latitude}, {hass.config.longitude}) | round }}}}'
    assert render(hass, tpl) == 187


def test_distance_function_with_1_state_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 state 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, '{{ distance("32.87336", "-117.22943", states.test.object_2) | round }}'
    )
    assert result == 187

    result = render(
        hass, '{{ distance(states.test.object_2, "32.87336", "-117.22943") | round }}'
    )
    assert result == 187


def test_distance_function_return_none_if_invalid_state(hass: HomeAssistant) -> None:
    """Test distance function return None if invalid state."""
    hass.states.async_set("test.object_2", "happy", {"latitude": 10})
    with pytest.raises(TemplateError):
        render(hass, "{{ distance(states.test.object_2) | round }}")


def test_distance_function_return_none_if_invalid_coord(hass: HomeAssistant) -> None:
    """Test distance function return None if invalid coord."""
    assert render(hass, '{{ distance("123", "abc") }}') is None

    assert render(hass, '{{ distance("123") }}') is None

    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(hass, '{{ distance("123", states.test_object_2) }}')
    assert result is None


def test_distance_function_with_2_entity_ids(hass: HomeAssistant) -> None:
    """Test distance function with 2 entity ids."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object", "happy", {"latitude": 32.87336, "longitude": -117.22943}
    )
    hass.states.async_set(
        "test.object_2",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(hass, '{{ distance("test.object", "test.object_2") | round }}')
    assert result == 187


def test_distance_function_with_1_entity_1_coord(hass: HomeAssistant) -> None:
    """Test distance function with 1 entity_id and 1 coord."""
    _set_up_units(hass)
    hass.states.async_set(
        "test.object",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    result = render(
        hass, '{{ distance("test.object", "32.87336", "-117.22943") | round }}'
    )
    assert result == 187


def test_closest_function_home_vs_domain(hass: HomeAssistant) -> None:
    """Test closest function home vs domain."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_test_domain.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert (
        render(hass, "{{ closest(states.test_domain).entity_id }}")
        == "test_domain.object"
    )

    assert (
        render(hass, "{{ (states.test_domain | closest).entity_id }}")
        == "test_domain.object"
    )


def test_closest_function_home_vs_all_states(hass: HomeAssistant) -> None:
    """Test closest function home vs all states."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain_2.and_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert render(hass, "{{ closest(states).entity_id }}") == "test_domain_2.and_closer"

    assert (
        render(hass, "{{ (states | closest).entity_id }}") == "test_domain_2.and_closer"
    )


async def test_expand(hass: HomeAssistant) -> None:
    """Test expand function."""
    info = render_to_info(hass, "{{ expand('test.object') }}")
    assert_result_info(info, [], ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ expand(56) }}")
    assert_result_info(info, [])
    assert info.rate_limit is None

    hass.states.async_set("test.object", "happy")

    info = render_to_info(
        hass,
        "{{ expand('test.object') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", ["test.object"])
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "", ["group.new_group"])
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand(states.group) | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "", [], ["group"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "new group",
        created_by_service=False,
        entity_ids=["test.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(
        hass,
        "{{ expand('group.new_group') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"group.new_group", "test.object"})
    assert info.rate_limit is None

    info = render_to_info(
        hass,
        "{{ expand(states.group) | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(info, "test.object", {"test.object"}, ["group"])
    assert info.rate_limit == DOMAIN_STATES_RATE_LIMIT

    info = render_to_info(
        hass,
        (
            "{{ expand('group.new_group', 'test.object')"
            " | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})

    info = render_to_info(
        hass,
        (
            "{{ ['group.new_group', 'test.object'] | expand"
            " | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}"
        ),
    )
    assert_result_info(info, "test.object", {"test.object", "group.new_group"})
    assert info.rate_limit is None

    hass.states.async_set("sensor.power_1", 0)
    hass.states.async_set("sensor.power_2", 200.2)
    hass.states.async_set("sensor.power_3", 400.4)

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "power sensors",
        created_by_service=False,
        entity_ids=["sensor.power_1", "sensor.power_2", "sensor.power_3"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(
        hass,
        (
            "{{ states.group.power_sensors.attributes.entity_id | expand "
            "| sort(attribute='entity_id') | map(attribute='state')|map('float')|sum  }}"
        ),
    )
    assert_result_info(
        info,
        200.2 + 400.4,
        {"group.power_sensors", "sensor.power_1", "sensor.power_2", "sensor.power_3"},
    )
    assert info.rate_limit is None

    # With group entities
    hass.states.async_set("light.first", "on")
    hass.states.async_set("light.second", "off")

    assert await async_setup_component(
        hass,
        "light",
        {
            "light": {
                "platform": "group",
                "name": "Grouped",
                "entities": ["light.first", "light.second"],
            }
        },
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('light.grouped') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "light.first, light.second",
        ["light.grouped", "light.first", "light.second"],
    )

    assert await async_setup_component(
        hass,
        "zone",
        {
            "zone": {
                "name": "Test",
                "latitude": 32.880837,
                "longitude": -117.237561,
                "radius": 250,
                "passive": False,
            }
        },
    )
    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "",
        ["zone.test"],
    )

    hass.states.async_set(
        "person.person1",
        "test",
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "person.person1",
        ["zone.test", "person.person1"],
    )

    hass.states.async_set(
        "person.person2",
        "test",
    )
    await hass.async_block_till_done()

    info = render_to_info(
        hass,
        "{{ expand('zone.test') | sort(attribute='entity_id') | map(attribute='entity_id') | join(', ') }}",
    )
    assert_result_info(
        info,
        "person.person1, person.person2",
        ["zone.test", "person.person1", "person.person2"],
    )


def test_closest_function_to_coord(hass: HomeAssistant) -> None:
    """Test closest function to coord."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    result = render(
        hass,
        f'{{{{ closest("{hass.config.latitude + 0.3}", {hass.config.longitude + 0.3}, states.test_domain).entity_id }}}}',
    )
    assert result == "test_domain.closest_zone"

    result = render(
        hass,
        f'{{{{ (states.test_domain | closest("{hass.config.latitude + 0.3}", {hass.config.longitude + 0.3})).entity_id }}}}',
    )
    assert result == "test_domain.closest_zone"


def test_closest_function_to_entity_id(hass: HomeAssistant) -> None:
    """Test closest function to entity id."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    info = render_to_info(
        hass,
        "{{ closest(zone, states.test_domain).entity_id }}",
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )

    info = render_to_info(
        hass,
        (
            "{{ ([states.test_domain, 'test_domain.closest_zone'] "
            "| closest(zone)).entity_id }}"
        ),
        {"zone": "zone.far_away"},
    )

    assert_result_info(
        info,
        "test_domain.closest_zone",
        ["test_domain.closest_home", "test_domain.closest_zone", "zone.far_away"],
        ["test_domain"],
    )


def test_closest_function_to_state(hass: HomeAssistant) -> None:
    """Test closest function to state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "test_domain.closest_zone",
        "happy",
        {
            "latitude": hass.config.latitude + 0.2,
            "longitude": hass.config.longitude + 0.2,
        },
    )

    hass.states.async_set(
        "zone.far_away",
        "zoning",
        {
            "latitude": hass.config.latitude + 0.3,
            "longitude": hass.config.longitude + 0.3,
        },
    )

    assert (
        render(
            hass, "{{ closest(states.zone.far_away, states.test_domain).entity_id }}"
        )
        == "test_domain.closest_zone"
    )


def test_closest_function_invalid_state(hass: HomeAssistant) -> None:
    """Test closest function invalid state."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    for state in ("states.zone.non_existing", '"zone.non_existing"'):
        assert render(hass, f"{{{{ closest({state}, states) }}}}") is None


def test_closest_function_state_with_invalid_location(hass: HomeAssistant) -> None:
    """Test closest function state with invalid location."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {"latitude": "invalid latitude", "longitude": hass.config.longitude + 0.1},
    )

    assert (
        render(hass, "{{ closest(states.test_domain.closest_home, states) }}") is None
    )


def test_closest_function_invalid_coordinates(hass: HomeAssistant) -> None:
    """Test closest function invalid coordinates."""
    hass.states.async_set(
        "test_domain.closest_home",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    assert render(hass, '{{ closest("invalid", "coord", states) }}') is None
    assert render(hass, '{{ states | closest("invalid", "coord") }}') is None


def test_closest_function_no_location_states(hass: HomeAssistant) -> None:
    """Test closest function without location states."""
    assert render(hass, "{{ closest(states).entity_id }}") == ""


def test_generate_filter_iterators(hass: HomeAssistant) -> None:
    """Test extract entities function with none entities stuff."""
    info = render_to_info(
        hass,
        """
        {% for state in states %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", all_states=True)

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "", domains=["sensor"])

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})

    # Don't need the entity because the state is not accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor", domains=["sensor"])

    # But we do here because the state gets accessed
    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.state }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=off,", [], ["sensor"])

    info = render_to_info(
        hass,
        """
        {% for state in states.sensor %}
        {{ state.entity_id }}={{ state.attributes.attr }},
        {% endfor %}
        """,
    )
    assert_result_info(info, "sensor.test_sensor=value,", [], ["sensor"])


def test_generate_select(hass: HomeAssistant) -> None:
    """Test extract entities function with none entities stuff."""
    template_str = """
{{ states.sensor|selectattr("state","equalto","off")
|join(",", attribute="entity_id") }}
        """

    info = render_to_info(hass, template_str)
    assert_result_info(info, "", [], [])
    assert info.domains_lifecycle == {"sensor"}

    hass.states.async_set("sensor.test_sensor", "off", {"attr": "value"})
    hass.states.async_set("sensor.test_sensor_on", "on")

    info = render_to_info(hass, template_str)
    assert_result_info(
        info,
        "sensor.test_sensor",
        [],
        ["sensor"],
    )
    assert info.domains_lifecycle == {"sensor"}


def test_state_with_unit(hass: HomeAssistant) -> None:
    """Test the state_with_unit property helper."""
    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "wow")

    result = render(hass, "{{ states.sensor.test.state_with_unit }}")
    assert result == "23 beers"

    result = render(hass, "{{ states.sensor.test2.state_with_unit }}")
    assert result == "wow"

    result = render(
        hass, "{% for state in states %}{{ state.state_with_unit }} {% endfor %}"
    )
    assert result == "23 beers wow"

    result = render(hass, "{{ states.sensor.non_existing.state_with_unit }}")
    assert result == ""


def test_state_with_unit_and_rounding(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test formatting the state rounded and with unit."""
    entry = entity_registry.async_get_or_create(
        "sensor", "test", "very_unique", suggested_object_id="test"
    )
    entity_registry.async_update_entity_options(
        entry.entity_id,
        "sensor",
        {
            "suggested_display_precision": 2,
        },
    )
    assert entry.entity_id == "sensor.test"

    hass.states.async_set("sensor.test", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test3", "-0.0", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test4", "-0", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    # state_with_unit property
    tpl = template.Template("{{ states.sensor.test.state_with_unit }}", hass)
    tpl2 = template.Template("{{ states.sensor.test2.state_with_unit }}", hass)

    # AllStates.__call__ defaults
    tpl3 = template.Template("{{ states('sensor.test') }}", hass)
    tpl4 = template.Template("{{ states('sensor.test2') }}", hass)

    # AllStates.__call__ and with_unit=True
    tpl5 = template.Template("{{ states('sensor.test', with_unit=True) }}", hass)
    tpl6 = template.Template("{{ states('sensor.test2', with_unit=True) }}", hass)

    # AllStates.__call__ and rounded=True
    tpl7 = template.Template("{{ states('sensor.test', rounded=True) }}", hass)
    tpl8 = template.Template("{{ states('sensor.test2', rounded=True) }}", hass)
    tpl9 = template.Template("{{ states('sensor.test3', rounded=True) }}", hass)
    tpl10 = template.Template("{{ states('sensor.test4', rounded=True) }}", hass)

    assert tpl.async_render() == "23.00 beers"
    assert tpl2.async_render() == "23 beers"
    assert tpl3.async_render() == 23
    assert tpl4.async_render() == 23
    assert tpl5.async_render() == "23.00 beers"
    assert tpl6.async_render() == "23 beers"
    assert tpl7.async_render() == 23.0
    assert tpl8.async_render() == 23
    assert tpl9.async_render() == 0.0
    assert tpl10.async_render() == 0

    hass.states.async_set("sensor.test", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})
    hass.states.async_set("sensor.test2", "23.015", {ATTR_UNIT_OF_MEASUREMENT: "beers"})

    assert tpl.async_render() == "23.02 beers"
    assert tpl2.async_render() == "23.015 beers"
    assert tpl3.async_render() == 23.015
    assert tpl4.async_render() == 23.015
    assert tpl5.async_render() == "23.02 beers"
    assert tpl6.async_render() == "23.015 beers"
    assert tpl7.async_render() == 23.02
    assert tpl8.async_render() == 23.015


async def test_closest_function_home_vs_group_entity_id(hass: HomeAssistant) -> None:
    """Test closest function home vs group entity id."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "location group",
        created_by_service=False,
        entity_ids=["test_domain.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None


async def test_closest_function_home_vs_group_state(hass: HomeAssistant) -> None:
    """Test closest function home vs group state."""
    hass.states.async_set(
        "test_domain.object",
        "happy",
        {
            "latitude": hass.config.latitude + 0.1,
            "longitude": hass.config.longitude + 0.1,
        },
    )

    hass.states.async_set(
        "not_in_group.but_closer",
        "happy",
        {"latitude": hass.config.latitude, "longitude": hass.config.longitude},
    )

    assert await async_setup_component(hass, "group", {})
    await hass.async_block_till_done()
    await group.Group.async_create_group(
        hass,
        "location group",
        created_by_service=False,
        entity_ids=["test_domain.object"],
        icon=None,
        mode=None,
        object_id=None,
        order=None,
    )

    info = render_to_info(hass, '{{ closest("group.location_group").entity_id }}')
    assert_result_info(
        info, "test_domain.object", {"group.location_group", "test_domain.object"}
    )
    assert info.rate_limit is None

    info = render_to_info(hass, "{{ closest(states.group.location_group).entity_id }}")
    assert_result_info(
        info, "test_domain.object", {"test_domain.object", "group.location_group"}
    )
    assert info.rate_limit is None
