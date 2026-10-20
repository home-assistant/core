"""Test the ENGIE Belgium conditions."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.common import (
    TargetSupport,
    assert_condition_options_supported,
    assert_conditions_target_support,
)

from homeassistant.components import automation
from homeassistant.components.engie_be.condition import CONDITIONS
from homeassistant.components.engie_be.const import DOMAIN
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import BAN, automation_calls, engie_entity_id, setup_dynamic_entry

_BELOW_THRESHOLD_OPTIONS = {"threshold": {"type": "below", "value": {"number": 0.1}}}

_CONDITION_TARGET_SUPPORT: dict[str, TargetSupport] = dict.fromkeys(
    CONDITIONS, TargetSupport.STANDARD
)


def test_condition_target_support() -> None:
    """Certify the condition registry matches its declared target support."""
    assert_conditions_target_support(CONDITIONS, _CONDITION_TARGET_SUPPORT)


async def _async_setup_condition_automation(
    hass: HomeAssistant, condition_config: dict[str, Any]
) -> None:
    """Set up an automation gated by one ENGIE Belgium condition."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "trigger": "state",
                    "entity_id": "input_boolean.test",
                    "to": "on",
                },
                "condition": condition_config,
                "action": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("condition", "base_options"),
    [
        pytest.param(f"{DOMAIN}.epex_hour_price_is_negative", {}, id="hour_negative"),
        pytest.param(
            f"{DOMAIN}.epex_quarter_hour_price_is_negative",
            {},
            id="quarter_hour_negative",
        ),
        pytest.param(
            f"{DOMAIN}.epex_hour_price_meets_threshold",
            _BELOW_THRESHOLD_OPTIONS,
            id="hour_meets_threshold",
        ),
        pytest.param(
            f"{DOMAIN}.epex_quarter_hour_price_meets_threshold",
            _BELOW_THRESHOLD_OPTIONS,
            id="quarter_hour_meets_threshold",
        ),
    ],
)
async def test_condition_options_validation(
    hass: HomeAssistant, condition: str, base_options: dict[str, Any] | None
) -> None:
    """Test that each condition accepts the options its schema supports."""
    await assert_condition_options_supported(
        hass, condition, base_options, supports_behavior=True, supports_duration=True
    )


@pytest.mark.parametrize(
    ("condition_key", "unique_id", "other_unique_id"),
    [
        pytest.param(
            "epex_hour_price_is_negative",
            f"{BAN}_epex_negative",
            f"{BAN}_epex_negative_quarter_hour",
            id="hour",
        ),
        pytest.param(
            "epex_quarter_hour_price_is_negative",
            f"{BAN}_epex_negative_quarter_hour",
            f"{BAN}_epex_negative",
            id="quarter_hour",
        ),
    ],
)
async def test_negative_condition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    condition_key: str,
    unique_id: str,
    other_unique_id: str,
) -> None:
    """Test the negative conditions pass only for their own entity."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, "binary_sensor", unique_id)
    other_entity_id = engie_entity_id(entity_registry, "binary_sensor", other_unique_id)
    hass.states.async_set("input_boolean.test", "off")
    await _async_setup_condition_automation(
        hass,
        {
            "condition": f"{DOMAIN}.{condition_key}",
            "target": {"entity_id": entity_id},
        },
    )

    hass.states.async_set(entity_id, "off")
    hass.states.async_set(other_entity_id, "on")
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set("input_boolean.test", "off")
    hass.states.async_set(entity_id, "on")
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1


@pytest.mark.parametrize(
    (
        "condition_key",
        "unique_id",
        "other_unique_id",
        "threshold",
        "passing_value",
        "failing_value",
    ),
    [
        pytest.param(
            "epex_hour_price_meets_threshold",
            f"{BAN}_epex_current_hour",
            f"{BAN}_epex_next_hour",
            {"type": "below", "value": {"number": 0.1}},
            "0.05",
            "0.15",
            id="hour_below",
        ),
        pytest.param(
            "epex_hour_price_meets_threshold",
            f"{BAN}_epex_current_hour",
            f"{BAN}_epex_next_hour",
            {"type": "above", "value": {"number": 0.1}},
            "0.15",
            "0.05",
            id="hour_above",
        ),
        pytest.param(
            "epex_quarter_hour_price_meets_threshold",
            f"{BAN}_epex_current_quarter_hour",
            f"{BAN}_epex_next_quarter_hour",
            {"type": "below", "value": {"number": 0.1}},
            "0.05",
            "0.15",
            id="quarter_hour_below",
        ),
        pytest.param(
            "epex_quarter_hour_price_meets_threshold",
            f"{BAN}_epex_current_quarter_hour",
            f"{BAN}_epex_next_quarter_hour",
            {"type": "above", "value": {"number": 0.1}},
            "0.15",
            "0.05",
            id="quarter_hour_above",
        ),
    ],
)
async def test_threshold_condition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    condition_key: str,
    unique_id: str,
    other_unique_id: str,
    threshold: dict[str, Any],
    passing_value: str,
    failing_value: str,
) -> None:
    """Test the threshold conditions pass only for their own entity."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, "sensor", unique_id)
    other_entity_id = engie_entity_id(entity_registry, "sensor", other_unique_id)
    hass.states.async_set("input_boolean.test", "off")
    await _async_setup_condition_automation(
        hass,
        {
            "condition": f"{DOMAIN}.{condition_key}",
            "target": {"entity_id": entity_id},
            "options": {"threshold": threshold},
        },
    )

    hass.states.async_set(entity_id, failing_value)
    hass.states.async_set(other_entity_id, passing_value)
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set("input_boolean.test", "off")
    hass.states.async_set(entity_id, passing_value)
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1


@pytest.mark.parametrize(
    (
        "condition_key",
        "domain",
        "unique_id",
        "own_unique_id",
        "options",
        "passing_state",
    ),
    [
        pytest.param(
            "epex_hour_price_meets_threshold",
            "sensor",
            f"{BAN}_epex_next_hour",
            f"{BAN}_epex_current_hour",
            _BELOW_THRESHOLD_OPTIONS,
            "0.05",
            id="hour_threshold_targeting_next_hour",
        ),
        pytest.param(
            "epex_hour_price_is_negative",
            "binary_sensor",
            f"{BAN}_epex_negative_quarter_hour",
            f"{BAN}_epex_negative",
            {},
            STATE_ON,
            id="hour_negative_targeting_quarter_hour",
        ),
    ],
)
async def test_condition_ignores_mismatched_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    condition_key: str,
    domain: str,
    unique_id: str,
    own_unique_id: str,
    options: dict[str, Any],
    passing_state: str,
) -> None:
    """Test that a condition targeting an entity of another kind never passes."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, domain, unique_id)
    own_entity_id = engie_entity_id(entity_registry, domain, own_unique_id)
    hass.states.async_set("input_boolean.test", "off")
    await _async_setup_condition_automation(
        hass,
        {
            "condition": f"{DOMAIN}.{condition_key}",
            "target": {"entity_id": entity_id},
            "options": options,
        },
    )

    hass.states.async_set(entity_id, passing_state)
    hass.states.async_set(own_entity_id, passing_state)
    await hass.async_block_till_done()
    hass.states.async_set("input_boolean.test", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0
