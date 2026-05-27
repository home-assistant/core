"""The tests for the location automation."""

from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components import automation, zone
from homeassistant.const import ATTR_ENTITY_ID, ENTITY_MATCH_ALL, SERVICE_TURN_OFF
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.setup import async_setup_component

from tests.common import mock_component
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
