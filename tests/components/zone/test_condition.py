"""The tests for the location condition."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components.zone import condition as zone_condition
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
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


@pytest.mark.parametrize("entity_id", ["device_tracker.cat", "person.bob"])
async def test_zone_condition_prefers_in_zones_over_coordinates(
    hass: HomeAssistant, entity_id: str
) -> None:
    """Test the legacy zone condition prefers in_zones over coordinates.

    For device_tracker and person entities the ``in_zones`` attribute is
    authoritative; coordinates are only consulted as a fallback.
    """
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    # in_zones lists the zone but the coordinates are far away -> in_zones wins.
    hass.states.async_set(
        entity_id,
        "home",
        {"latitude": 50.0, "longitude": 50.0, "in_zones": ["zone.home"]},
    )
    assert zone_condition.zone(hass, "zone.home", entity_id) is True

    # in_zones is empty but the coordinates are inside the zone -> in_zones wins.
    hass.states.async_set(
        entity_id,
        "not_home",
        {"latitude": 2.1, "longitude": 1.1, "in_zones": []},
    )
    assert zone_condition.zone(hass, "zone.home", entity_id) is False

    # in_zones lists a different zone -> not in the target zone.
    hass.states.async_set(
        entity_id,
        "work",
        {"latitude": 2.1, "longitude": 1.1, "in_zones": ["zone.work"]},
    )
    assert zone_condition.zone(hass, "zone.home", entity_id) is False


async def test_zone_condition_ignores_in_zones_for_other_domains(
    hass: HomeAssistant,
) -> None:
    """Test in_zones is only honored for device_tracker and person entities.

    An entity in another domain that exposes an ``in_zones`` attribute is
    matched by coordinates instead.
    """
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    # in_zones claims the zone but the coordinates are far away -> coordinates win.
    hass.states.async_set(
        "sensor.tracker",
        "home",
        {"latitude": 50.0, "longitude": 50.0, "in_zones": ["zone.home"]},
    )
    assert zone_condition.zone(hass, "zone.home", "sensor.tracker") is False

    # in_zones is empty but the coordinates are inside the zone -> coordinates win.
    hass.states.async_set(
        "sensor.tracker",
        "home",
        {"latitude": 2.1, "longitude": 1.1, "in_zones": []},
    )
    assert zone_condition.zone(hass, "zone.home", "sensor.tracker") is True


async def test_zone_condition_falls_back_to_coordinates(hass: HomeAssistant) -> None:
    """Test the legacy zone condition uses coordinates without an in_zones attr.

    Coordinate-only entities (e.g. geo_location) report no ``in_zones``.
    """
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"name": "home", "latitude": 2.1, "longitude": 1.1, "radius": 10},
    )

    # Inside the zone by coordinates, no in_zones attribute.
    hass.states.async_set(
        "geo_location.quake",
        "1.0",
        {"latitude": 2.1, "longitude": 1.1},
    )
    assert zone_condition.zone(hass, "zone.home", "geo_location.quake") is True

    # Outside the zone by coordinates.
    hass.states.async_set(
        "geo_location.quake",
        "1.0",
        {"latitude": 50.0, "longitude": 50.0},
    )
    assert zone_condition.zone(hass, "zone.home", "geo_location.quake") is False


# --- New-style zone condition tests ---

ZONE_HOME = "zone.home"
ZONE_WORK = "zone.work"
IN_ZONES_HOME = {"in_zones": [ZONE_HOME]}
IN_ZONES_WORK = {"in_zones": [ZONE_WORK]}
IN_ZONES_NONE: dict[str, list[str]] = {"in_zones": []}
TARGET_ZONE = ZONE_HOME


@pytest.mark.parametrize(
    (
        "condition_key",
        "base_options",
        "supports_behavior",
        "supports_duration",
        "supports_target",
    ),
    [
        ("zone.in_zone", {"zone": TARGET_ZONE}, True, True, True),
        ("zone.not_in_zone", {"zone": TARGET_ZONE}, True, True, True),
        ("zone.occupancy_is_detected", {"zone": ZONE_HOME}, False, True, False),
        ("zone.occupancy_is_not_detected", {"zone": ZONE_HOME}, False, True, False),
    ],
)
async def test_zone_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
    supports_target: bool,
) -> None:
    """Test that zone conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
        supports_target=supports_target,
    )


@pytest.mark.parametrize(
    ("condition_key", "config"),
    [
        (
            "zone.in_zone",
            {"target": {"entity_id": "person.alice"}, "options": {"zone": "light.x"}},
        ),
        (
            "zone.not_in_zone",
            {"target": {"entity_id": "person.alice"}, "options": {"zone": "light.x"}},
        ),
        (
            "zone.occupancy_is_detected",
            {"options": {"zone": "light.x"}},
        ),
        (
            "zone.occupancy_is_not_detected",
            {"options": {"zone": "light.x"}},
        ),
    ],
)
async def test_zone_condition_rejects_non_zone_entity_id(
    hass: HomeAssistant, condition_key: str, config: dict[str, Any]
) -> None:
    """Test that the zone option must reference entities in the zone domain."""
    with pytest.raises(vol.Invalid):
        await condition.async_validate_condition_config(
            hass,
            {"condition": condition_key, **config},
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


async def test_in_zone_condition_for_attribute_only_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test `for:` anchors to in_zones updates, not state.state changes.

    A person already "home" who enters an overlapping zone (e.g. zone.coffee)
    keeps state.state == "home" while in_zones grows. `for: 5m` on
    in_zone(zone.coffee) must start counting from when in_zones changed, not
    from the (older) last state.state transition.
    """
    coffee_zone = "zone.coffee"

    # Person at home but not yet in the coffee zone.
    hass.states.async_set(
        "person.alice",
        "home",
        {"in_zones": [ZONE_HOME]},
    )
    await hass.async_block_till_done()

    # Time passes — state.state's last_changed sits 10 minutes in the past.
    freezer.tick(timedelta(minutes=10))

    config = await condition.async_validate_condition_config(
        hass,
        {
            "condition": "zone.in_zone",
            "target": {"entity_id": "person.alice"},
            "options": {"zone": coffee_zone, "for": {"minutes": 5}},
        },
    )
    test = await condition.async_from_config(hass, config)

    # in_zones gains the coffee zone; state.state stays "home", so last_changed
    # is untouched and only last_updated advances.
    hass.states.async_set(
        "person.alice",
        "home",
        {"in_zones": [ZONE_HOME, coffee_zone]},
    )
    await hass.async_block_till_done()

    # Just entered; `for: 5m` must not be satisfied yet. (Without value_source
    # set on the DomainSpec, the anchor would be last_changed from 10 minutes
    # ago and this would incorrectly evaluate to True.)
    assert test.async_check() is False

    # After the duration elapses, the condition is satisfied.
    freezer.tick(timedelta(minutes=6))
    assert test.async_check() is True


# --- Zone occupancy condition tests ---


@pytest.mark.parametrize(
    ("condition_key", "zone_state", "expected"),
    [
        # occupancy_is_detected — true when count >= 1
        pytest.param("zone.occupancy_is_detected", "1", True, id="detected_1"),
        pytest.param("zone.occupancy_is_detected", "3", True, id="detected_3"),
        pytest.param("zone.occupancy_is_detected", "0", False, id="detected_0"),
        pytest.param(
            "zone.occupancy_is_detected",
            STATE_UNAVAILABLE,
            False,
            id="detected_unavailable",
        ),
        pytest.param(
            "zone.occupancy_is_detected", STATE_UNKNOWN, False, id="detected_unknown"
        ),
        # occupancy_is_not_detected — true only when count == 0
        pytest.param("zone.occupancy_is_not_detected", "0", True, id="empty_0"),
        pytest.param("zone.occupancy_is_not_detected", "1", False, id="empty_1"),
        pytest.param("zone.occupancy_is_not_detected", "3", False, id="empty_3"),
        # Unavailable / unknown are not "empty" — they're indeterminate.
        pytest.param(
            "zone.occupancy_is_not_detected",
            STATE_UNAVAILABLE,
            False,
            id="empty_unavailable",
        ),
        pytest.param(
            "zone.occupancy_is_not_detected",
            STATE_UNKNOWN,
            False,
            id="empty_unknown",
        ),
    ],
)
async def test_zone_occupancy_condition_evaluates(
    hass: HomeAssistant,
    condition_key: str,
    zone_state: str,
    expected: bool,
) -> None:
    """Test occupancy conditions evaluate against the zone's integer state."""
    hass.states.async_set(ZONE_HOME, zone_state)
    await hass.async_block_till_done()

    config = await condition.async_validate_condition_config(
        hass, {"condition": condition_key, "options": {"zone": ZONE_HOME}}
    )
    test = await condition.async_from_config(hass, config)
    assert test.async_check() is expected
