"""Tests for the Lutron Caseta integration."""

from unittest.mock import AsyncMock

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

    class MockBridgeWithSmartAway(MockBridge):
        """Mock bridge with smart away support."""

        def __init__(self, can_connect=True, timeout_on_connect=False):
            """Initialize mock bridge with smart away."""
            super().__init__(can_connect, timeout_on_connect)
            self.smart_away_state = "Disabled"
            self._smart_away_subscribers = []

        def add_smart_away_subscriber(self, callback):
            """Add a smart away subscriber."""
            self._smart_away_subscribers.append(callback)

        async def activate_smart_away(self):
            """Activate smart away."""
            self.smart_away_state = "Enabled"
            for callback in self._smart_away_subscribers:
                callback()

        async def deactivate_smart_away(self):
            """Deactivate smart away."""
            self.smart_away_state = "Disabled"
            for callback in self._smart_away_subscribers:
                callback()

    await async_setup_integration(hass, MockBridgeWithSmartAway)

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify entity is registered
    entity_entry = entity_registry.async_get(smart_away_entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == "1234"

    # Verify initial state is off
    state = hass.states.get(smart_away_entity_id)
    assert state is not None
    assert state.state == STATE_OFF

async def test_smart_away_switch_not_created_when_not_supported(
        hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test smart away switch is not created when bridge doesn't support it."""

    class MockBridgeWithoutSmartAway(MockBridge):
        """Mock bridge without smart away support."""

        def __init__(self, can_connect=True, timeout_on_connect=False):
            super().__init__(can_connect, timeout_on_connect)
            self.smart_away_state = ""

    await async_setup_integration(hass, MockBridgeWithoutSmartAway)

    smart_away_entity_id = "switch.hallway_smart_away"

    # Verify entity is not registered
    entity_entry = entity_registry.async_get(smart_away_entity_id)
    assert entity_entry is None

    # Verify state doesn't exist
    state = hass.states.get(smart_away_entity_id)
    assert state is None

async def test_smart_away_turn_on(hass: HomeAssistant) -> None:
    """Test turning on smart away."""

    class MockBridgeWithSmartAway(MockBridge):
        """Mock bridge with smart away support."""

        def __init__(self, can_connect=True, timeout_on_connect=False):
            """Initialize mock bridge with smart away."""
            super().__init__(can_connect, timeout_on_connect)
            self.smart_away_state = "Disabled"
            self._smart_away_subscribers = []
            self.activate_smart_away = AsyncMock(side_effect=self._activate)
            self.deactivate_smart_away = AsyncMock(side_effect=self._deactivate)

        def add_smart_away_subscriber(self, callback):
            """Add a smart away subscriber."""
            self._smart_away_subscribers.append(callback)

        async def _activate(self):
            """Activate smart away."""
            self.smart_away_state = "Enabled"
            for callback in self._smart_away_subscribers:
                callback()

        async def _deactivate(self):
            """Deactivate smart away."""
            self.smart_away_state = "Disabled"
            for callback in self._smart_away_subscribers:
                callback()

    await async_setup_integration(hass, MockBridgeWithSmartAway)

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

    class MockBridgeWithSmartAway(MockBridge):
        """Mock bridge with smart away support."""

        def __init__(self, can_connect=True, timeout_on_connect=False):
            """Initialize mock bridge with smart away."""
            super().__init__(can_connect, timeout_on_connect)
            self.smart_away_state = "Enabled"
            self._smart_away_subscribers = []
            self.activate_smart_away = AsyncMock(side_effect=self._activate)
            self.deactivate_smart_away = AsyncMock(side_effect=self._deactivate)

        def add_smart_away_subscriber(self, callback):
            """Add a smart away subscriber."""
            self._smart_away_subscribers.append(callback)

        async def _activate(self):
            """Activate smart away."""
            self.smart_away_state = "Enabled"
            for callback in self._smart_away_subscribers:
                callback()

        async def _deactivate(self):
            """Deactivate smart away."""
            self.smart_away_state = "Disabled"
            for callback in self._smart_away_subscribers:
                callback()

    await async_setup_integration(hass, MockBridgeWithSmartAway)

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
