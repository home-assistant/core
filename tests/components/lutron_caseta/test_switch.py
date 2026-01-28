"""Tests for the Lutron Caseta integration."""

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockBridge, async_setup_integration


async def test_switch_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test a light unique id."""
    await async_setup_integration(hass, MockBridge)

    switch_entity_id = "switch.basement_bathroom_exhaust_fan"

    # Assert that Caseta covers will have the bridge serial hash and the zone id as the uniqueID
    assert entity_registry.async_get(switch_entity_id).unique_id == "000004d2_803"


async def test_smart_away_switch_setup(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test smart away switch is created when bridge supports it."""
    await async_setup_integration(hass, MockBridge, smart_away_state="Disabled")

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify entity is registered
    entity_entry = entity_registry.async_get(smart_away_entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == "000004d2_smart_away"

    # Verify initial state is off
    state = hass.states.get(smart_away_entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_smart_away_switch_not_created_when_not_supported(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test smart away switch is not created when bridge doesn't support it."""

    await async_setup_integration(hass, MockBridge)

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify entity is not registered
    entity_entry = entity_registry.async_get(smart_away_entity_id)
    assert entity_entry is None

    # Verify state doesn't exist
    state = hass.states.get(smart_away_entity_id)
    assert state is None


async def test_smart_away_turn_on(hass: HomeAssistant) -> None:
    """Test turning on smart away."""

    await async_setup_integration(hass, MockBridge, smart_away_state="Disabled")

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify initial state is off
    state = hass.states.get(smart_away_entity_id)
    assert state.state == STATE_OFF

    # Turn on smart away
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: smart_away_entity_id},
        blocking=True,
    )

    # Verify state is on
    state = hass.states.get(smart_away_entity_id)
    assert state.state == STATE_ON


async def test_smart_away_turn_off(hass: HomeAssistant) -> None:
    """Test turning off smart away."""

    await async_setup_integration(hass, MockBridge, smart_away_state="Enabled")

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify initial state is off
    state = hass.states.get(smart_away_entity_id)
    assert state.state == STATE_ON

    # Turn on smart away
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: smart_away_entity_id},
        blocking=True,
    )

    # Verify state is on
    state = hass.states.get(smart_away_entity_id)
    assert state.state == STATE_OFF
