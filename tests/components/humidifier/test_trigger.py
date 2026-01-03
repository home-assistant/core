"""Test humidifier trigger."""

from collections.abc import Generator
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.humidifier.const import (
    ATTR_ACTION,
    ATTR_CURRENT_HUMIDITY,
    HumidifierAction,
)
from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.trigger import (
    CONF_LOWER_LIMIT,
    CONF_THRESHOLD_TYPE,
    CONF_UPPER_LIMIT,
    ThresholdType,
)

from tests.components import (
    StateDescription,
    arm_trigger,
    parametrize_target_entities,
    parametrize_trigger_states,
    set_or_remove_state,
    target_entities,
)


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture(name="enable_experimental_triggers_conditions")
def enable_experimental_triggers_conditions() -> Generator[None]:
    """Enable experimental triggers and conditions."""
    with patch(
        "homeassistant.components.labs.async_is_preview_feature_enabled",
        return_value=True,
    ):
        yield


@pytest.fixture
async def target_humidifiers(hass: HomeAssistant) -> list[str]:
    """Create multiple humidifier entities associated with different targets."""
    return (await target_entities(hass, "humidifier"))["included"]


@pytest.mark.parametrize(
    "trigger_key",
    [
        "humidifier.current_humidity_changed",
        "humidifier.current_humidity_crossed_threshold",
        "humidifier.started_drying",
        "humidifier.started_humidifying",
        "humidifier.turned_off",
        "humidifier.turned_on",
    ],
)
async def test_humidifier_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the humidifier triggers are gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


def parametrize_humidifier_trigger_states(
    *,
    trigger: str,
    trigger_options: dict | None = None,
    target_states: list[str | None | tuple[str | None, dict]],
    other_states: list[str | None | tuple[str | None, dict]],
    additional_attributes: dict | None = None,
    trigger_from_none: bool = True,
    retrigger_on_target_state: bool = False,
) -> list[tuple[str, dict[str, Any], list[StateDescription]]]:
    """Parametrize states and expected service call counts."""
    trigger_options = trigger_options or {}
    return [
        (s[0], trigger_options, *s[1:])
        for s in parametrize_trigger_states(
            trigger=trigger,
            target_states=target_states,
            other_states=other_states,
            additional_attributes=additional_attributes,
            trigger_from_none=trigger_from_none,
            retrigger_on_target_state=retrigger_on_target_state,
        )
    ]


def parametrize_xxx_changed_trigger_states(
    trigger: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[StateDescription]]]:
    """Parametrize states and expected service call counts for xxx_changed triggers."""
    return [
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={},
            target_states=[
                (STATE_ON, {attribute: 0}),
                (STATE_ON, {attribute: 50}),
                (STATE_ON, {attribute: 100}),
            ],
            other_states=[(STATE_ON, {attribute: None})],
            retrigger_on_target_state=True,
        ),
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={CONF_ABOVE: 10},
            target_states=[
                (STATE_ON, {attribute: 50}),
                (STATE_ON, {attribute: 100}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 0}),
            ],
            retrigger_on_target_state=True,
        ),
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={CONF_BELOW: 90},
            target_states=[
                (STATE_ON, {attribute: 0}),
                (STATE_ON, {attribute: 50}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 100}),
            ],
            retrigger_on_target_state=True,
        ),
    ]


def parametrize_xxx_crossed_threshold_trigger_states(
    trigger: str, attribute: str
) -> list[tuple[str, dict[str, Any], list[StateDescription]]]:
    """Parametrize states and expected service call counts for xxx_crossed_threshold triggers."""
    return [
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BETWEEN,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (STATE_ON, {attribute: 50}),
                (STATE_ON, {attribute: 60}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 0}),
                (STATE_ON, {attribute: 100}),
            ],
        ),
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.OUTSIDE,
                CONF_LOWER_LIMIT: 10,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (STATE_ON, {attribute: 0}),
                (STATE_ON, {attribute: 100}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 50}),
                (STATE_ON, {attribute: 60}),
            ],
        ),
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.ABOVE,
                CONF_LOWER_LIMIT: 10,
            },
            target_states=[
                (STATE_ON, {attribute: 50}),
                (STATE_ON, {attribute: 100}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 0}),
            ],
        ),
        *parametrize_humidifier_trigger_states(
            trigger=trigger,
            trigger_options={
                CONF_THRESHOLD_TYPE: ThresholdType.BELOW,
                CONF_UPPER_LIMIT: 90,
            },
            target_states=[
                (STATE_ON, {attribute: 0}),
                (STATE_ON, {attribute: 50}),
            ],
            other_states=[
                (STATE_ON, {attribute: None}),
                (STATE_ON, {attribute: 100}),
            ],
        ),
    ]


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the humidifier state trigger fires when any humidifier state changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other humidifiers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_xxx_changed_trigger_states(
            "humidifier.current_humidity_changed", ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_xxx_crossed_threshold_trigger_states(
            "humidifier.current_humidity_crossed_threshold", ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[StateDescription],
) -> None:
    """Test that the humidifier state trigger fires when any humidifier state changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, trigger_options, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other humidifiers also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the humidifier state trigger fires when the first humidifier changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "first"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other humidifiers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_xxx_crossed_threshold_trigger_states(
            "humidifier.current_humidity_crossed_threshold", ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the humidifier state trigger fires when the first humidifier state changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "first"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Triggering other humidifiers should not cause the trigger to fire again
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        *parametrize_trigger_states(
            trigger="humidifier.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="humidifier.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_humidifier_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the humidifier state trigger fires when the last humidifier changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, {"behavior": "last"}, trigger_target_config)

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("humidifier"),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_xxx_crossed_threshold_trigger_states(
            "humidifier.current_humidity_crossed_threshold", ATTR_CURRENT_HUMIDITY
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_drying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.DRYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
        *parametrize_humidifier_trigger_states(
            trigger="humidifier.started_humidifying",
            target_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.HUMIDIFYING})],
            other_states=[(STATE_ON, {ATTR_ACTION: HumidifierAction.IDLE})],
        ),
    ],
)
async def test_humidifier_state_attribute_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_humidifiers: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[tuple[tuple[str, dict], int]],
) -> None:
    """Test that the humidifier state trigger fires when the last humidifier state changes to a specific state."""
    other_entity_ids = set(target_humidifiers) - {entity_id}

    # Set all humidifiers, including the tested humidifier, to the initial state
    for eid in target_humidifiers:
        set_or_remove_state(hass, eid, states[0]["included"])
        await hass.async_block_till_done()

    await arm_trigger(
        hass, trigger, {"behavior": "last"} | trigger_options, trigger_target_config
    )

    for state in states[1:]:
        included_state = state["included"]
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, included_state)
            await hass.async_block_till_done()
        assert len(service_calls) == 0

        set_or_remove_state(hass, entity_id, included_state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()
