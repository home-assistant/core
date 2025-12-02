"""The tests for components."""

from enum import StrEnum
import itertools
from typing import TypedDict

from homeassistant.const import (
    ATTR_AREA_ID,
    ATTR_DEVICE_ID,
    ATTR_FLOOR_ID,
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_PLATFORM,
    CONF_TARGET,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_device_registry


async def target_entities(
    hass: HomeAssistant, domain: str
) -> tuple[list[str], list[str]]:
    """Create multiple entities associated with different targets.

    Returns a dict with the following keys:
    - included: List of entity_ids meant to be targeted.
    - excluded: List of entity_ids not meant to be targeted.
    """
    await async_setup_component(hass, domain, {})

    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)

    floor_reg = fr.async_get(hass)
    floor = floor_reg.async_get_floor_by_name("Test Floor") or floor_reg.async_create(
        "Test Floor"
    )

    area_reg = ar.async_get(hass)
    area = area_reg.async_get_area_by_name("Test Area") or area_reg.async_create(
        "Test Area", floor_id=floor.floor_id
    )

    label_reg = lr.async_get(hass)
    label = label_reg.async_get_label_by_name("Test Label") or label_reg.async_create(
        "Test Label"
    )

    device = dr.DeviceEntry(id="test_device", area_id=area.id, labels={label.label_id})
    mock_device_registry(hass, {device.id: device})

    entity_reg = er.async_get(hass)
    # Entities associated with area
    entity_area = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area",
        suggested_object_id=f"area_{domain}",
    )
    entity_reg.async_update_entity(entity_area.entity_id, area_id=area.id)
    entity_area_excluded = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_area_excluded",
        suggested_object_id=f"area_{domain}_excluded",
    )
    entity_reg.async_update_entity(entity_area_excluded.entity_id, area_id=area.id)

    # Entities associated with device
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device",
        suggested_object_id=f"device_{domain}",
        device_id=device.id,
    )
    entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_device_excluded",
        suggested_object_id=f"device_{domain}_excluded",
        device_id=device.id,
    )

    # Entities associated with label
    entity_label = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label",
        suggested_object_id=f"label_{domain}",
    )
    entity_reg.async_update_entity(entity_label.entity_id, labels={label.label_id})
    entity_label_excluded = entity_reg.async_get_or_create(
        domain=domain,
        platform="test",
        unique_id=f"{domain}_label_excluded",
        suggested_object_id=f"label_{domain}_excluded",
    )
    entity_reg.async_update_entity(
        entity_label_excluded.entity_id, labels={label.label_id}
    )

    # Return all available entities
    return {
        "included": [
            f"{domain}.standalone_{domain}",
            f"{domain}.label_{domain}",
            f"{domain}.area_{domain}",
            f"{domain}.device_{domain}",
        ],
        "excluded": [
            f"{domain}.standalone_{domain}_excluded",
            f"{domain}.label_{domain}_excluded",
            f"{domain}.area_{domain}_excluded",
            f"{domain}.device_{domain}_excluded",
        ],
    }


def parametrize_target_entities(domain: str) -> list[tuple[dict, str, int]]:
    """Parametrize target entities for different target types.

    Meant to be used with target_entities.
    """
    return [
        (
            {CONF_ENTITY_ID: f"{domain}.standalone_{domain}"},
            f"{domain}.standalone_{domain}",
            1,
        ),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.label_{domain}", 2),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.area_{domain}", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.area_{domain}", 2),
        ({ATTR_LABEL_ID: "test_label"}, f"{domain}.device_{domain}", 2),
        ({ATTR_AREA_ID: "test_area"}, f"{domain}.device_{domain}", 2),
        ({ATTR_FLOOR_ID: "test_floor"}, f"{domain}.device_{domain}", 2),
        ({ATTR_DEVICE_ID: "test_device"}, f"{domain}.device_{domain}", 1),
    ]


class _StateDescription(TypedDict):
    """Test state and expected service call count."""

    state: str | None
    attributes: dict


class StateDescription(TypedDict):
    """Test state and expected service call count."""

    included: _StateDescription
    excluded: _StateDescription
    count: int


def parametrize_trigger_states(
    *,
    trigger: str,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    additional_attributes: dict | None = None,
    trigger_from_none: bool = True,
) -> list[tuple[str, list[StateDescription]]]:
    """Parametrize states and expected service call counts.

    The target_states and other_states iterables are either iterables of
    states or iterables of (state, attributes) tuples.

    Set `trigger_from_none` to False if the trigger is not expected to fire
    when the initial state is None.

    Returns a list of tuples with (trigger, list of states),
    where states is a list of StateDescription dicts.
    """

    additional_attributes = additional_attributes or {}

    def state_with_attributes(
        state: str | None | tuple[str | None, dict], count: int
    ) -> dict:
        """Return (state, attributes) dict."""
        if isinstance(state, str) or state is None:
            return {
                "included": {
                    "state": state,
                    "attributes": additional_attributes,
                },
                "excluded": {
                    "state": state,
                    "attributes": {},
                },
                "count": count,
            }
        return {
            "included": {
                "state": state[0],
                "attributes": state[1] | additional_attributes,
            },
            "excluded": {
                "state": state[0],
                "attributes": state[1],
            },
            "count": count,
        }

    return [
        # Initial state None
        (
            trigger,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(None, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(
                            target_state, 1 if trigger_from_none else 0
                        ),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Initial state different from target state
        (
            trigger,
            # other_state,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Initial state same as target state
        (
            trigger,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(target_state, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        # Initial state unavailable / unknown
        (
            trigger,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(STATE_UNAVAILABLE, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
        (
            trigger,
            list(
                itertools.chain.from_iterable(
                    (
                        state_with_attributes(STATE_UNKNOWN, 0),
                        state_with_attributes(target_state, 0),
                        state_with_attributes(other_state, 0),
                        state_with_attributes(target_state, 1),
                    )
                    for target_state in target_states
                    for other_state in other_states
                )
            ),
        ),
    ]


async def arm_trigger(
    hass: HomeAssistant,
    trigger: str,
    trigger_options: dict | None,
    trigger_target: dict,
) -> None:
    """Arm the specified trigger, call service test.automation when it triggers."""

    # Local include to avoid importing the automation component unnecessarily
    from homeassistant.components import automation  # noqa: PLC0415

    options = {CONF_OPTIONS: {**trigger_options}} if trigger_options is not None else {}

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    CONF_PLATFORM: trigger,
                    CONF_TARGET: {**trigger_target},
                }
                | options,
                "action": {
                    "service": "test.automation",
                    "data_template": {CONF_ENTITY_ID: "{{ trigger.entity_id }}"},
                },
            }
        },
    )


def set_or_remove_state(
    hass: HomeAssistant,
    entity_id: str,
    state: StateDescription,
) -> None:
    """Set or remove the state of an entity."""
    if state["state"] is None:
        hass.states.async_remove(entity_id)
    else:
        hass.states.async_set(
            entity_id, state["state"], state["attributes"], force_update=True
        )


def other_states(state: StrEnum) -> list[str]:
    """Return a sorted list with all states except the specified one."""
    return sorted({s.value for s in state.__class__} - {state.value})
