"""The tests for the location condition."""

from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.zone import condition as zone_condition
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConditionError
from homeassistant.helpers import condition, config_validation as cv

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_options_supported,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


async def test_zone_raises(hass: HomeAssistant) -> None:
    """Test that zone raises ConditionError on errors."""
    config = {
        "condition": "zone",
        "options": {"entity_id": "device_tracker.cat", "zone": "zone.home"},
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError, match="no zone"):
        zone_condition.zone(hass, zone_ent=None, entity="sensor.any")

    with pytest.raises(ConditionError, match="unknown zone"):
        test.async_check()

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    with pytest.raises(ConditionError, match="no entity"):
        zone_condition.zone(hass, zone_ent="zone.home", entity=None)

    with pytest.raises(ConditionError, match="unknown entity"):
        test.async_check()

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat"},
    )

    with pytest.raises(ConditionError, match="latitude"):
        test.async_check()

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat", "latitude": 2.1},
    )

    with pytest.raises(ConditionError, match="longitude"):
        test.async_check()

    hass.states.async_set(
        "device_tracker.cat",
        "home",
        {"friendly_name": "cat", "latitude": 2.1, "longitude": 1.1},
    )

    # All okay, now test multiple failed conditions
    assert test.async_check()

    config = {
        "condition": "zone",
        "options": {
            "entity_id": ["device_tracker.cat", "device_tracker.dog"],
            "zone": ["zone.home", "zone.work"],
        },
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    with pytest.raises(ConditionError, match="dog"):
        test.async_check()

    with pytest.raises(ConditionError, match="work"):
        test.async_check()

    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 20, "longitude": 10, "radius": 25000},
    )

    hass.states.async_set(
        "device_tracker.dog",
        "work",
        {"friendly_name": "dog", "latitude": 20.1, "longitude": 10.1},
    )

    assert test.async_check()


async def test_zone_multiple_entities(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "alias": "Zone Condition",
                "condition": "zone",
                "options": {
                    "entity_id": ["device_tracker.person_1", "device_tracker.person_2"],
                    "zone": "zone.home",
                },
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert test.async_check()

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 20.1, "longitude": 10.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 2.1, "longitude": 1.1},
    )
    assert not test.async_check()

    hass.states.async_set(
        "device_tracker.person_1",
        "home",
        {"friendly_name": "person_1", "latitude": 2.1, "longitude": 1.1},
    )
    hass.states.async_set(
        "device_tracker.person_2",
        "home",
        {"friendly_name": "person_2", "latitude": 20.1, "longitude": 10.1},
    )
    assert not test.async_check()


async def test_multiple_zones(hass: HomeAssistant) -> None:
    """Test with multiple entities in condition."""
    config = {
        "condition": "and",
        "conditions": [
            {
                "condition": "zone",
                "options": {
                    "entity_id": "device_tracker.person",
                    "zone": ["zone.home", "zone.work"],
                },
            },
        ],
    }
    config = cv.CONDITION_SCHEMA(config)
    config = await condition.async_validate_condition_config(hass, config)
    test = await condition.async_from_config(hass, config)

    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )
    hass.states.async_set(
        "zone.work",
        "zoning",
        {"name": "work", "latitude": 20.1, "longitude": 10.1, "radius": 10},
    )

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 2.1, "longitude": 1.1},
    )
    assert test.async_check()

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 20.1, "longitude": 10.1},
    )
    assert test.async_check()

    hass.states.async_set(
        "device_tracker.person",
        "home",
        {"friendly_name": "person", "latitude": 50.1, "longitude": 20.1},
    )
    assert not test.async_check()


# --- New-style zone condition tests ---

ZONE_HOME = "zone.home"
ZONE_WORK = "zone.work"
IN_ZONES_HOME = {"in_zones": [ZONE_HOME]}
IN_ZONES_WORK = {"in_zones": [ZONE_WORK]}
IN_ZONES_NONE: dict[str, list[str]] = {"in_zones": []}
TARGET_ZONE = ZONE_HOME


@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("zone.in_zone", {"zone": TARGET_ZONE}, True, True),
        ("zone.not_in_zone", {"zone": TARGET_ZONE}, True, True),
    ],
)
async def test_zone_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that zone conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.parametrize("condition_key", ["zone.in_zone", "zone.not_in_zone"])
async def test_zone_condition_rejects_non_zone_entity_id(
    hass: HomeAssistant, condition_key: str
) -> None:
    """Test that the zone option must reference entities in the zone domain."""
    with pytest.raises(vol.Invalid):
        await condition.async_validate_condition_config(
            hass,
            {
                "condition": condition_key,
                "target": {"entity_id": "person.alice"},
                "options": {"zone": "person.alice"},
            },
        )


@pytest.fixture
async def target_zone_entities(
    hass: HomeAssistant, domain: str
) -> dict[str, list[str]]:
    """Create multiple zone-trackable entities associated with different targets."""
    return await target_entities(hass, domain, domain_excluded="sensor")


# `in_zone` is True for states where the entity carries the target zone in
# `in_zones`; `not_in_zone` flips the relation.
_ZONE_CONDITION_STATES_ANY = [
    *parametrize_condition_states_any(
        condition="zone.in_zone",
        condition_options={"zone": TARGET_ZONE},
        target_states=[
            ("home", IN_ZONES_HOME),
        ],
        other_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
        excluded_entities_from_other_domain=True,
    ),
    *parametrize_condition_states_any(
        condition="zone.not_in_zone",
        condition_options={"zone": TARGET_ZONE},
        target_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
        other_states=[
            ("home", IN_ZONES_HOME),
        ],
        excluded_entities_from_other_domain=True,
    ),
]


_ZONE_CONDITION_STATES_ALL = [
    *parametrize_condition_states_all(
        condition="zone.in_zone",
        condition_options={"zone": TARGET_ZONE},
        target_states=[
            ("home", IN_ZONES_HOME),
        ],
        other_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
        excluded_entities_from_other_domain=True,
    ),
    *parametrize_condition_states_all(
        condition="zone.not_in_zone",
        condition_options={"zone": TARGET_ZONE},
        target_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
        other_states=[
            ("home", IN_ZONES_HOME),
        ],
        excluded_entities_from_other_domain=True,
    ),
]


def _parametrize_zone_target_entities() -> list[tuple[dict[str, Any], str, int, str]]:
    """Parametrize target entities for all supported zone condition domains."""
    return [
        (*params, domain)
        for domain in ("person", "device_tracker")
        for params in parametrize_target_entities(domain)
    ]


@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target", "domain"),
    _parametrize_zone_target_entities(),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    _ZONE_CONDITION_STATES_ANY,
)
async def test_zone_condition_behavior_any(
    hass: HomeAssistant,
    target_zone_entities: dict[str, list[str]],
    condition_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test zone conditions under behavior=any."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_zone_entities,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target", "domain"),
    _parametrize_zone_target_entities(),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    _ZONE_CONDITION_STATES_ALL,
)
async def test_zone_condition_behavior_all(
    hass: HomeAssistant,
    target_zone_entities: dict[str, list[str]],
    condition_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test zone conditions under behavior=all."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_zone_entities,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
