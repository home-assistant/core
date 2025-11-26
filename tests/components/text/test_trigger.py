"""Test text trigger."""

from collections.abc import Generator
from unittest.mock import patch

import pytest

from homeassistant.const import (
    ATTR_LABEL_ID,
    CONF_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component

from tests.components import (
    StateDescription,
    arm_trigger,
    parametrize_target_entities,
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
async def target_texts(hass: HomeAssistant) -> list[str]:
    """Create multiple text entities associated with different targets."""
    return await target_entities(hass, "text")


@pytest.mark.parametrize("trigger_key", ["text.changed"])
async def test_text_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the text.changed trigger is gated by the labs flag."""
    await arm_trigger(hass, trigger_key, None, {ATTR_LABEL_ID: "test_label"})
    assert (
        "Unnamed automation failed to setup triggers and has been disabled: Trigger "
        f"'{trigger_key}' requires the experimental 'New triggers and conditions' "
        "feature to be enabled in Home Assistant Labs settings (feature flag: "
        "'new_triggers_conditions')"
    ) in caplog.text


@pytest.mark.usefixtures("enable_experimental_triggers_conditions")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("text"),
)
@pytest.mark.parametrize(
    ("trigger", "states"),
    [
        (
            "text.changed",
            [
                {"state": None, "attributes": {}, "count": 0},
                {"state": "bar", "attributes": {}, "count": 0},
                {"state": "baz", "attributes": {}, "count": 1},
            ],
        ),
        (
            "text.changed",
            [
                {"state": "foo", "attributes": {}, "count": 0},
                {"state": "bar", "attributes": {}, "count": 1},
                {"state": "baz", "attributes": {}, "count": 1},
            ],
        ),
        (
            "text.changed",
            [
                {"state": "foo", "attributes": {}, "count": 0},
                {"state": "", "attributes": {}, "count": 1},  # empty string
                {"state": "baz", "attributes": {}, "count": 1},
            ],
        ),
        (
            "text.changed",
            [
                {"state": STATE_UNAVAILABLE, "attributes": {}, "count": 0},
                {"state": "bar", "attributes": {}, "count": 0},
                {"state": "baz", "attributes": {}, "count": 1},
                {"state": STATE_UNAVAILABLE, "attributes": {}, "count": 0},
            ],
        ),
        (
            "text.changed",
            [
                {"state": STATE_UNKNOWN, "attributes": {}, "count": 0},
                {"state": "bar", "attributes": {}, "count": 0},
                {"state": "baz", "attributes": {}, "count": 1},
                {"state": STATE_UNKNOWN, "attributes": {}, "count": 0},
            ],
        ),
    ],
)
async def test_text_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_texts: list[str],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    states: list[StateDescription],
) -> None:
    """Test that the text state trigger fires when any text state changes to a specific state."""
    await async_setup_component(hass, "text", {})

    other_entity_ids = set(target_texts) - {entity_id}

    # Set all texts, including the tested text, to the initial state
    for eid in target_texts:
        set_or_remove_state(hass, eid, states[0])
        await hass.async_block_till_done()

    await arm_trigger(hass, trigger, None, trigger_target_config)

    for state in states[1:]:
        set_or_remove_state(hass, entity_id, state)
        await hass.async_block_till_done()
        assert len(service_calls) == state["count"]
        for service_call in service_calls:
            assert service_call.data[CONF_ENTITY_ID] == entity_id
        service_calls.clear()

        # Check if changing other texts also triggers
        for other_entity_id in other_entity_ids:
            set_or_remove_state(hass, other_entity_id, state)
            await hass.async_block_till_done()
        assert len(service_calls) == (entities_in_target - 1) * state["count"]
        service_calls.clear()
