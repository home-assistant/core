"""Test the ENGIE Belgium triggers."""

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.common import (
    TargetSupport,
    assert_trigger_options_supported,
    assert_triggers_target_support,
)

from homeassistant.components import automation
from homeassistant.components.engie_be.const import DOMAIN, EPEX_SCAN_INTERVAL
from homeassistant.components.engie_be.trigger import TRIGGERS
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import (
    BAN,
    automation_calls,
    build_epex_payload,
    build_epex_payload_without_tomorrow,
    engie_entity_id,
    setup_dynamic_entry,
)

_CROSSED_THRESHOLD_OPTIONS = {"threshold": {"type": "above", "value": {"number": 0.2}}}

_TRIGGER_TARGET_SUPPORT: dict[str, TargetSupport] = dict.fromkeys(
    TRIGGERS, TargetSupport.STANDARD
)


def test_trigger_target_support() -> None:
    """Certify the trigger registry matches its declared target support."""
    assert_triggers_target_support(TRIGGERS, _TRIGGER_TARGET_SUPPORT)


async def _async_setup_trigger_automation(
    hass: HomeAssistant, trigger_config: dict[str, Any]
) -> None:
    """Set up an automation with one ENGIE Belgium trigger."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": trigger_config,
                "action": {"action": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("trigger", "base_options", "supports_behavior", "supports_duration"),
    [
        *(
            pytest.param(f"{DOMAIN}.{key}", {}, True, True, id=key)
            for key in (
                "epex_hour_became_negative",
                "epex_hour_no_longer_negative",
                "epex_quarter_hour_became_negative",
                "epex_quarter_hour_no_longer_negative",
                "epex_tomorrow_prices_published",
            )
        ),
        *(
            pytest.param(
                f"{DOMAIN}.{key}", _CROSSED_THRESHOLD_OPTIONS, True, True, id=key
            )
            for key in (
                "epex_current_hour_crossed_threshold",
                "epex_next_hour_crossed_threshold",
                "epex_current_quarter_hour_crossed_threshold",
                "epex_next_quarter_hour_crossed_threshold",
            )
        ),
        *(
            pytest.param(f"{DOMAIN}.{key}", {}, False, False, id=key)
            for key in (
                "epex_high_today_hour_updated",
                "epex_low_today_hour_updated",
                "epex_high_today_quarter_hour_updated",
                "epex_low_today_quarter_hour_updated",
            )
        ),
    ],
)
async def test_trigger_options_validation(
    hass: HomeAssistant,
    trigger: str,
    base_options: dict[str, Any] | None,
    supports_behavior: bool,
    supports_duration: bool,
) -> None:
    """Test that each trigger accepts the options its schema supports."""
    await assert_trigger_options_supported(
        hass,
        trigger,
        base_options,
        supports_behavior=supports_behavior,
        supports_duration=supports_duration,
    )


@pytest.mark.parametrize(
    ("trigger_key", "unique_id", "other_unique_id", "fire_state", "hold_state"),
    [
        pytest.param(
            "epex_hour_became_negative",
            f"{BAN}_epex_negative",
            f"{BAN}_epex_negative_quarter_hour",
            STATE_ON,
            STATE_OFF,
            id="hour_became",
        ),
        pytest.param(
            "epex_hour_no_longer_negative",
            f"{BAN}_epex_negative",
            f"{BAN}_epex_negative_quarter_hour",
            STATE_OFF,
            STATE_ON,
            id="hour_no_longer",
        ),
        pytest.param(
            "epex_quarter_hour_became_negative",
            f"{BAN}_epex_negative_quarter_hour",
            f"{BAN}_epex_negative",
            STATE_ON,
            STATE_OFF,
            id="quarter_hour_became",
        ),
        pytest.param(
            "epex_quarter_hour_no_longer_negative",
            f"{BAN}_epex_negative_quarter_hour",
            f"{BAN}_epex_negative",
            STATE_OFF,
            STATE_ON,
            id="quarter_hour_no_longer",
        ),
    ],
)
async def test_binary_edge_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    unique_id: str,
    other_unique_id: str,
    fire_state: str,
    hold_state: str,
) -> None:
    """Test the binary edge triggers fire only for their own entity and edge."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, "binary_sensor", unique_id)
    other_entity_id = engie_entity_id(entity_registry, "binary_sensor", other_unique_id)
    await _async_setup_trigger_automation(
        hass,
        {"trigger": f"{DOMAIN}.{trigger_key}", "target": {"entity_id": entity_id}},
    )

    hass.states.async_set(other_entity_id, fire_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(entity_id, hold_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(entity_id, fire_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, fire_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1


@pytest.mark.parametrize(
    ("trigger_key", "unique_id", "other_unique_id"),
    [
        pytest.param(
            "epex_current_hour_crossed_threshold",
            f"{BAN}_epex_current_hour",
            f"{BAN}_epex_next_hour",
            id="current_hour",
        ),
        pytest.param(
            "epex_next_hour_crossed_threshold",
            f"{BAN}_epex_next_hour",
            f"{BAN}_epex_current_hour",
            id="next_hour",
        ),
        pytest.param(
            "epex_current_quarter_hour_crossed_threshold",
            f"{BAN}_epex_current_quarter_hour",
            f"{BAN}_epex_next_quarter_hour",
            id="current_quarter_hour",
        ),
        pytest.param(
            "epex_next_quarter_hour_crossed_threshold",
            f"{BAN}_epex_next_quarter_hour",
            f"{BAN}_epex_current_quarter_hour",
            id="next_quarter_hour",
        ),
    ],
)
async def test_crossed_threshold_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    unique_id: str,
    other_unique_id: str,
) -> None:
    """Test the threshold triggers fire only when their own entity crosses."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, "sensor", unique_id)
    other_entity_id = engie_entity_id(entity_registry, "sensor", other_unique_id)
    await _async_setup_trigger_automation(
        hass,
        {
            "trigger": f"{DOMAIN}.{trigger_key}",
            "target": {"entity_id": entity_id},
            "options": _CROSSED_THRESHOLD_OPTIONS,
        },
    )

    hass.states.async_set(other_entity_id, "0.25")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(entity_id, "0.15")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(entity_id, "0.25")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, "0.3")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, "0.15")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, "0.25")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 2


@pytest.mark.parametrize(
    ("trigger_key", "unique_id", "other_unique_id"),
    [
        pytest.param(
            "epex_high_today_hour_updated",
            f"{BAN}_epex_high_today_hour",
            f"{BAN}_epex_low_today_hour",
            id="high_hour",
        ),
        pytest.param(
            "epex_low_today_hour_updated",
            f"{BAN}_epex_low_today_hour",
            f"{BAN}_epex_high_today_hour",
            id="low_hour",
        ),
        pytest.param(
            "epex_high_today_quarter_hour_updated",
            f"{BAN}_epex_high_today_quarter_hour",
            f"{BAN}_epex_low_today_quarter_hour",
            id="high_quarter_hour",
        ),
        pytest.param(
            "epex_low_today_quarter_hour_updated",
            f"{BAN}_epex_low_today_quarter_hour",
            f"{BAN}_epex_high_today_quarter_hour",
            id="low_quarter_hour",
        ),
    ],
)
async def test_updated_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    unique_id: str,
    other_unique_id: str,
) -> None:
    """Test the updated triggers fire on every state change of their entity."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, "sensor", unique_id)
    other_entity_id = engie_entity_id(entity_registry, "sensor", other_unique_id)
    state = hass.states.get(entity_id)
    assert state is not None
    value = float(state.state)
    await _async_setup_trigger_automation(
        hass,
        {"trigger": f"{DOMAIN}.{trigger_key}", "target": {"entity_id": entity_id}},
    )

    hass.states.async_set(other_entity_id, str(value + 5))
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(entity_id, str(value + 1))
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, str(value + 1))
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1

    hass.states.async_set(entity_id, str(value + 2))
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 2


@pytest.mark.usefixtures("frozen_afternoon")
async def test_tomorrow_prices_published_trigger(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    service_calls: list[ServiceCall],
) -> None:
    """Test the trigger fires when tomorrow's prices become available."""
    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload_without_tomorrow
    )
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(
        entity_registry, "binary_sensor", f"{BAN}_epex_tomorrow_available"
    )
    await _async_setup_trigger_automation(
        hass,
        {
            "trigger": f"{DOMAIN}.epex_tomorrow_prices_published",
            "target": {"entity_id": entity_id},
        },
    )

    mock_engie_client.return_value.async_get_epex_prices.side_effect = (
        build_epex_payload
    )
    freezer.tick(EPEX_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 1


async def test_trigger_ignores_foreign_entity(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    service_calls: list[ServiceCall],
) -> None:
    """Test a trigger targeting a non-ENGIE entity never fires."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    hass.states.async_set("sensor.foreign_price", "off")
    await _async_setup_trigger_automation(
        hass,
        {
            "trigger": f"{DOMAIN}.epex_hour_became_negative",
            "target": {"entity_id": "sensor.foreign_price"},
        },
    )

    hass.states.async_set("sensor.foreign_price", "on")
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0


@pytest.mark.parametrize(
    (
        "trigger_key",
        "domain",
        "unique_id",
        "own_unique_id",
        "hold_state",
        "fire_state",
        "options",
    ),
    [
        pytest.param(
            "epex_current_hour_crossed_threshold",
            "sensor",
            f"{BAN}_epex_next_hour",
            f"{BAN}_epex_current_hour",
            "0.15",
            "0.25",
            _CROSSED_THRESHOLD_OPTIONS,
            id="hour_threshold_targeting_next_hour",
        ),
        pytest.param(
            "epex_hour_became_negative",
            "binary_sensor",
            f"{BAN}_epex_negative_quarter_hour",
            f"{BAN}_epex_negative",
            STATE_OFF,
            STATE_ON,
            {},
            id="hour_negative_targeting_quarter_hour",
        ),
    ],
)
async def test_trigger_ignores_mismatched_target(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_engie_client: MagicMock,
    entity_registry: er.EntityRegistry,
    service_calls: list[ServiceCall],
    trigger_key: str,
    domain: str,
    unique_id: str,
    own_unique_id: str,
    hold_state: str,
    fire_state: str,
    options: dict[str, Any],
) -> None:
    """Test that a trigger targeting an entity of another kind never fires."""
    await setup_dynamic_entry(hass, mock_config_entry, mock_engie_client)
    entity_id = engie_entity_id(entity_registry, domain, unique_id)
    own_entity_id = engie_entity_id(entity_registry, domain, own_unique_id)
    await _async_setup_trigger_automation(
        hass,
        {
            "trigger": f"{DOMAIN}.{trigger_key}",
            "target": {"entity_id": entity_id},
            "options": options,
        },
    )

    hass.states.async_set(entity_id, hold_state)
    await hass.async_block_till_done()
    hass.states.async_set(entity_id, fire_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0

    hass.states.async_set(own_entity_id, hold_state)
    await hass.async_block_till_done()
    hass.states.async_set(own_entity_id, fire_state)
    await hass.async_block_till_done()
    assert len(automation_calls(service_calls)) == 0
