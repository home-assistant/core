"""Test remote conditions."""

from typing import Any

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.components.common import (
    ConditionStateDescription,
    assert_condition_behavior_all,
    assert_condition_behavior_any,
    assert_condition_gated_by_labs_flag,
    assert_condition_options_supported,
    parametrize_condition_states_all,
    parametrize_condition_states_any,
    parametrize_target_entities,
    target_entities,
)


@pytest.fixture
async def target_remotes(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple remote entities associated with different targets."""
    return await target_entities(hass, "remote", domain_excluded="switch")


@pytest.mark.parametrize(
    "condition",
    [
        "remote.is_off",
        "remote.is_on",
    ],
)
async def test_remote_conditions_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, condition: str
) -> None:
    """Test the remote conditions are gated by the labs flag."""
    await assert_condition_gated_by_labs_flag(hass, caplog, condition)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_key", "base_options", "supports_behavior", "supports_duration"),
    [
        ("remote.is_off", {}, True, True),
        ("remote.is_on", {}, True, True),
    ],
)
async def test_remote_condition_options_validation(
    hass: HomeAssistant,
    condition_key: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that remote conditions support the expected options."""
    await assert_condition_options_supported(
        hass,
        condition_key,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("condition_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities("remote"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_any(
            condition="remote.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            excluded_entities_from_other_domain=True,
        ),
        *parametrize_condition_states_any(
            condition="remote.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_remote_state_condition_behavior_any(
    hass: HomeAssistant,
    target_remotes: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the remote state condition with the 'any' behavior."""
    await assert_condition_behavior_any(
        hass,
        target_entities=target_remotes,
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
    parametrize_target_entities("remote"),
)
@pytest.mark.parametrize(
    ("condition", "condition_options", "states"),
    [
        *parametrize_condition_states_all(
            condition="remote.is_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
            excluded_entities_from_other_domain=True,
        ),
        *parametrize_condition_states_all(
            condition="remote.is_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
            excluded_entities_from_other_domain=True,
        ),
    ],
)
async def test_remote_state_condition_behavior_all(
    hass: HomeAssistant,
    target_remotes: dict[str, list[str]],
    condition_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    condition: str,
    condition_options: dict[str, Any],
    states: list[ConditionStateDescription],
) -> None:
    """Test the remote state condition with the 'all' behavior."""
    await assert_condition_behavior_all(
        hass,
        target_entities=target_remotes,
        condition_target_config=condition_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        condition=condition,
        condition_options=condition_options,
        states=states,
    )
