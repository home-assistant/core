"""Test text conditions."""

from typing import Any

import pytest

from homeassistant.components.text.condition import CONF_VALUE
from homeassistant.const import (
    CONF_CONDITION,
    CONF_ENTITY_ID,
    CONF_OPTIONS,
    CONF_TARGET,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.condition import (
    async_from_config as async_condition_from_config,
)

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_texts(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple text entities associated with different targets."""
    return await target_entities(hass, "text")


@pytest.fixture
async def target_input_texts(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple input_text entities associated with different targets."""
    return await target_entities(hass, "input_text")


@pytest.mark.parametrize("condition", ["text.is_equal_to"])
async def test_text_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the text conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


CONDITION_STATES_ANY = [
    *parametrize_condition_states_any(
        condition="text.is_equal_to",
        condition_options={CONF_VALUE: "hello"},
        target_states=["hello"],
        other_states=["world"],
    ),
]

CONDITION_STATES_ALL = [
    *parametrize_condition_states_all(
        condition="text.is_equal_to",
        condition_options={CONF_VALUE: "hello"},
        target_states=["hello"],
        other_states=["world"],
    ),
]


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("text"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"), CONDITION_STATES_ANY
)
async def test_text_condition_behavior_any(
    hass: HomeAssistant,
    target_texts: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the text is_equal_to condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_texts,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_text"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"), CONDITION_STATES_ANY
)
async def test_input_text_condition_behavior_any(
    hass: HomeAssistant,
    target_input_texts: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the text is_equal_to condition with input_text and the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_input_texts,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("text"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"), CONDITION_STATES_ALL
)
async def test_text_condition_behavior_all(
    hass: HomeAssistant,
    target_texts: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the text is_equal_to condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_texts,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("input_text"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"), CONDITION_STATES_ALL
)
async def test_input_text_condition_behavior_all(
    hass: HomeAssistant,
    target_input_texts: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the text is_equal_to condition with input_text and the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_input_texts,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )


# --- Cross-domain test ---


@pytest.mark.usefixtures("enable_labs_preview_features")
async def test_text_condition_fires_for_both_domains(
    hass: HomeAssistant,
) -> None:
    """Test that the text condition works for both text and input_text entities."""
    entity_id_text = "text.test_text"
    entity_id_input_text = "input_text.test_input_text"

    hass.states.async_set(entity_id_text, "hello")
    hass.states.async_set(entity_id_input_text, "hello")
    await hass.async_block_till_done()

    checker = await async_condition_from_config(
        hass,
        {
            CONF_CONDITION: "text.is_equal_to",
            CONF_TARGET: {
                CONF_ENTITY_ID: [entity_id_text, entity_id_input_text],
            },
            CONF_OPTIONS: {"behavior": "all", CONF_VALUE: "hello"},
        },
    )

    assert checker(hass) is True

    # Change input_text to non-matching - all behavior should fail
    hass.states.async_set(entity_id_input_text, "world")
    await hass.async_block_till_done()
    assert checker(hass) is False
