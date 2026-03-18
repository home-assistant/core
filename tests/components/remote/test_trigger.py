"""Test remote trigger."""

from typing import Any

import pytest

from homeassistant.components.remote import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall

from tests.components.common import (
    TriggerStateDescription,
    assert_trigger_behavior_any,
    assert_trigger_behavior_first,
    assert_trigger_behavior_last,
    assert_trigger_gated_by_labs_flag,
    parametrize_target_entities,
    parametrize_trigger_states,
    target_entities,
)


@pytest.fixture
async def target_remotes(hass: HomeAssistant) -> dict[str, list[str]]:
    """Create multiple remotes entities associated with different targets."""
    return await target_entities(hass, DOMAIN)


@pytest.mark.parametrize(
    "trigger_key",
    ["remote.turned_on", "remote.turned_off"],
)
async def test_remote_triggers_gated_by_labs_flag(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, trigger_key: str
) -> None:
    """Test the remote triggers are gated by the labs flag."""
    await assert_trigger_gated_by_labs_flag(hass, caplog, trigger_key)


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="remote.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="remote.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_remote_state_trigger_behavior_any(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_remotes: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the remote triggers when any remote changes to a specific state."""
    await assert_trigger_behavior_any(
        hass,
        service_calls=service_calls,
        target_entities=target_remotes,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="remote.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="remote.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_remote_state_trigger_behavior_first(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_remotes: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the remote triggers when the first remote changes to a specific state."""
    await assert_trigger_behavior_first(
        hass,
        service_calls=service_calls,
        target_entities=target_remotes,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )


@pytest.mark.usefixtures("enable_labs_preview_features")
@pytest.mark.parametrize(
    ("trigger_target_config", "entity_id", "entities_in_target"),
    parametrize_target_entities(DOMAIN),
)
@pytest.mark.parametrize(
    ("trigger", "trigger_options", "states"),
    [
        *parametrize_trigger_states(
            trigger="remote.turned_on",
            target_states=[STATE_ON],
            other_states=[STATE_OFF],
        ),
        *parametrize_trigger_states(
            trigger="remote.turned_off",
            target_states=[STATE_OFF],
            other_states=[STATE_ON],
        ),
    ],
)
async def test_remote_state_trigger_behavior_last(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    target_remotes: dict[str, list[str]],
    trigger_target_config: dict,
    entity_id: str,
    entities_in_target: int,
    trigger: str,
    trigger_options: dict[str, Any],
    states: list[TriggerStateDescription],
) -> None:
    """Test that the remote triggers when the last remote changes to a specific state."""
    await assert_trigger_behavior_last(
        hass,
        service_calls=service_calls,
        target_entities=target_remotes,
        trigger_target_config=trigger_target_config,
        entity_id=entity_id,
        entities_in_target=entities_in_target,
        trigger=trigger,
        trigger_options=trigger_options,
        states=states,
    )
