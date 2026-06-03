"""The tests for the location automation."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest
import voluptuous as vol

from homeassistant.components import automation, zone
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.setup import async_setup_component

from tests.common import async_fire_time_changed, mock_component
from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_all,
    assert_trigger_behavior_each,
    assert_trigger_behavior_first,
    assert_trigger_options_supported,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")
    await async_setup_component(
        hass,
        zone.DOMAIN,
        {
            "zone": {
                "name": "test",
                "latitude": 32.880837,
                "longitude": -117.237561,
                "radius": 250,
            }
        },
    )


async def test_if_fires_on_zone_enter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for firing on zone enter."""
    context = Context()
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.zone.name }}"
                            " - {{ trigger.id }}"
                        )
                    },
                },
            }
        },
    )

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id
    assert (
        service_calls[0].data["some"] == "zone - test.entity - hello - hello - test - 0"
    )

    # Set out of zone again so we can trigger call
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 2


async def test_if_fires_on_zone_enter_uuid(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
) -> None:
    """Test for firing on zone enter when device is specified by entity registry id."""
    context = Context()

    entry = entity_registry.async_get_or_create(
        "test", "hue", "1234", suggested_object_id="entity"
    )
    assert entry.entity_id == "test.entity"

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": entry.id,
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.zone.name }}"
                            " - {{ trigger.id }}"
                        )
                    },
                },
            }
        },
    )

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].context.parent_id == context.id
    assert (
        service_calls[0].data["some"] == "zone - test.entity - hello - hello - test - 0"
    )

    # Set out of zone again so we can trigger call
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(service_calls) == 2

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 2


async def test_if_not_fires_for_enter_on_zone_leave(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for not firing on zone leave."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "enter",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_if_fires_on_zone_leave(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for firing on zone leave."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_if_not_fires_for_leave_on_zone_enter(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for not firing on zone enter."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                    "event": "leave",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 0


async def test_zone_condition(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test for zone condition."""
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.880586, "longitude": -117.237564}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": {
                    "condition": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.test",
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(service_calls) == 1


async def test_unknown_zone(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for firing on zone enter."""
    context = Context()
    hass.states.async_set(
        "test.entity", "hello", {"latitude": 32.881011, "longitude": -117.234758}
    )
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "alias": "My Automation",
                "trigger": {
                    "platform": "zone",
                    "entity_id": "test.entity",
                    "zone": "zone.no_such_zone",
                    "event": "enter",
                },
                "action": {
                    "service": "test.automation",
                },
            }
        },
    )

    assert "Non-existing zone 'zone.no_such_zone' in a zone trigger" not in caplog.text

    hass.states.async_set(
        "test.entity",
        "hello",
        {"latitude": 32.880586, "longitude": -117.237564},
        context=context,
    )
    await hass.async_block_till_done()

    assert "Non-existing zone 'zone.no_such_zone' in a zone trigger" in caplog.text


# --- New-style zone trigger tests ---

ZONE_HOME = "zone.home"
ZONE_WORK = "zone.work"
IN_ZONES_HOME = {"in_zones": [ZONE_HOME]}
IN_ZONES_WORK = {"in_zones": [ZONE_WORK]}
IN_ZONES_NONE: dict[str, list[str]] = {"in_zones": []}
TRIGGER_ZONE = ZONE_HOME


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("zone.entered", {"zone": TRIGGER_ZONE}, True, True),
        ("zone.left", {"zone": TRIGGER_ZONE}, True, True),
    ],
)
async def test_zone_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that zone triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.parametrize("trigger_key", ["zone.entered", "zone.left"])
async def test_zone_trigger_rejects_non_zone_entity_id(
    hass: HomeAssistant, trigger_key: str
) -> None:
    """Test that the zone option must reference entities in the zone domain."""
    with pytest.raises(vol.Invalid):
        await async_validate_trigger_config(
            hass,
            [
                {
                    "platform": trigger_key,
                    "target": {"entity_id": "person.alice"},
                    "options": {"zone": "person.alice"},
                }
            ],
        )


@pytest.fixture
async def target_zone_entities(
    hass: HomeAssistant, domain: str
) -> dict[str, list[str]]:
    """Create multiple zone-trackable entities associated with different targets."""
    return await target_entities(hass, domain, domain_excluded="sensor")


_ZONE_TRIGGER_STATES = [
    *parametrize_trigger_states(
        trigger="zone.entered",
        trigger_options={"zone": TRIGGER_ZONE},
        target_states=[
            ("home", IN_ZONES_HOME),
        ],
        other_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
    ),
    *parametrize_trigger_states(
        trigger="zone.left",
        trigger_options={"zone": TRIGGER_ZONE},
        target_states=[
            ("not_home", IN_ZONES_NONE),
            ("Work", IN_ZONES_WORK),
        ],
        other_states=[
            ("home", IN_ZONES_HOME),
        ],
    ),
]


def _parametrize_zone_target_entities() -> list[tuple[dict[str, Any], str, int, str]]:
    """Parametrize target entities for all supported zone trigger domains."""
    return [
        (*params, domain)
        for domain in ("person", "device_tracker")
        for params in parametrize_target_entities(domain)
    ]


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target", "domain"),
    _parametrize_zone_target_entities(),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    _ZONE_TRIGGER_STATES,
)
async def test_zone_trigger_behavior_each(
    hass: HomeAssistant,
    target_zone_entities: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test zone triggers fire when any targeted entity changes."""
    await assert_trigger_behavior_each(
        hass,
        target_entities=target_zone_entities,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target", "domain"),
    _parametrize_zone_target_entities(),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    _ZONE_TRIGGER_STATES,
)
async def test_zone_trigger_behavior_first(
    hass: HomeAssistant,
    target_zone_entities: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test zone triggers fire when first targeted entity changes."""
    await assert_trigger_behavior_first(
        hass,
        target_entities=target_zone_entities,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target", "domain"),
    _parametrize_zone_target_entities(),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    _ZONE_TRIGGER_STATES,
)
async def test_zone_trigger_behavior_all(
    hass: HomeAssistant,
    target_zone_entities: dict[str, list[str]],
    trigger_target_config: dict[str, Any],
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test zone triggers fire when last targeted entity changes."""
    await assert_trigger_behavior_all(
        hass,
        target_entities=target_zone_entities,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


# --- Zone occupancy trigger tests ---


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key"),
    ["zone.occupancy_detected", "zone.occupancy_cleared"],
)
async def test_zone_occupancy_trigger_options_validation(
    hass: HomeAssistant,
    trigger_key: str,
) -> None:
    """Test that occupancy triggers support the expected options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        {"zone": ZONE_HOME},
        supports_behavior=False,
        supports_duration=True,
        supports_target=False,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "from_state", "to_state", "should_fire"),
    [
        # occupancy_detected
        pytest.param("zone.occupancy_detected", "0", "1", True, id="detected_0_to_1"),
        pytest.param("zone.occupancy_detected", "0", "3", True, id="detected_0_to_3"),
        pytest.param("zone.occupancy_detected", "1", "2", False, id="detected_1_to_2"),
        pytest.param("zone.occupancy_detected", "2", "0", False, id="detected_2_to_0"),
        pytest.param(
            "zone.occupancy_detected",
            STATE_UNKNOWN,
            "1",
            False,
            id="detected_unknown_to_1",
        ),
        pytest.param(
            "zone.occupancy_detected",
            STATE_UNAVAILABLE,
            "1",
            False,
            id="detected_unavailable_to_1",
        ),
        pytest.param(
            "zone.occupancy_detected",
            "0",
            STATE_UNAVAILABLE,
            False,
            id="detected_0_to_unavailable",
        ),
        # occupancy_cleared
        pytest.param("zone.occupancy_cleared", "1", "0", True, id="cleared_1_to_0"),
        pytest.param("zone.occupancy_cleared", "3", "0", True, id="cleared_3_to_0"),
        pytest.param("zone.occupancy_cleared", "2", "1", False, id="cleared_2_to_1"),
        pytest.param("zone.occupancy_cleared", "0", "1", False, id="cleared_0_to_1"),
        pytest.param(
            "zone.occupancy_cleared",
            "1",
            STATE_UNAVAILABLE,
            False,
            id="cleared_1_to_unavailable",
        ),
        pytest.param(
            "zone.occupancy_cleared",
            "1",
            STATE_UNKNOWN,
            False,
            id="cleared_1_to_unknown",
        ),
    ],
)
async def test_zone_occupancy_trigger_transitions(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    from_state: str,
    to_state: str,
    should_fire: bool,
) -> None:
    """Test occupancy triggers fire on the expected numeric-state transitions."""
    hass.states.async_set(ZONE_HOME, from_state)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "trigger": trigger_key,
                    "options": {"zone": ZONE_HOME},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set(ZONE_HOME, to_state)
    await hass.async_block_till_done()
    assert (len(service_calls) == 1) is should_fire


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_key", "from_value", "to_value", "revert_value"),
    [
        ("zone.occupancy_detected", "0", "1", "0"),
        ("zone.occupancy_cleared", "1", "0", "1"),
    ],
)
async def test_zone_occupancy_trigger_for_duration(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
    trigger_key: str,
    from_value: str,
    to_value: str,
    revert_value: str,
) -> None:
    """Test that `for` delays the firing and an early revert cancels it."""
    hass.states.async_set(ZONE_HOME, from_value)
    await hass.async_block_till_done()

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "trigger": trigger_key,
                    "options": {"zone": ZONE_HOME, "for": {"seconds": 5}},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    # Transition, then revert before the duration elapses -> no fire.
    hass.states.async_set(ZONE_HOME, to_value)
    await hass.async_block_till_done()
    hass.states.async_set(ZONE_HOME, revert_value)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # Transition and hold past the duration -> fire once.
    hass.states.async_set(ZONE_HOME, to_value)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(service_calls) == 1
