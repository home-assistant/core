"""The tests for the demo switch component."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.kitchen_sink import DOMAIN
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

SWITCH_ENTITY_IDS = ["switch.outlet_1", "switch.outlet_2"]


@pytest.fixture
def switch_only() -> Generator[None]:
    """Enable only the switch platform."""
    with patch(
        "homeassistant.components.kitchen_sink.COMPONENTS_WITH_DEMO_PLATFORM",
        [Platform.SWITCH],
    ):
        yield


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant, switch_only: None) -> None:
    """Set up demo component."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()


async def test_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test switch state."""
    for entity_id in SWITCH_ENTITY_IDS:
        state = hass.states.get(entity_id)
        assert state == snapshot
        entity_entry = entity_registry.async_get(entity_id)
        assert entity_entry == snapshot
        sub_device_entry = device_registry.async_get(entity_entry.device_id)
        assert sub_device_entry == snapshot
        main_device_entry = device_registry.async_get(sub_device_entry.via_device_id)
        assert main_device_entry == snapshot


@pytest.mark.parametrize("switch_entity_id", SWITCH_ENTITY_IDS)
async def test_turn_on(hass: HomeAssistant, switch_entity_id: str) -> None:
    """Test switch turn on method."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    state = hass.states.get(switch_entity_id)
    assert state.state == STATE_OFF

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    state = hass.states.get(switch_entity_id)
    assert state.state == STATE_ON


@pytest.mark.parametrize("switch_entity_id", SWITCH_ENTITY_IDS)
async def test_turn_off(hass: HomeAssistant, switch_entity_id: str) -> None:
    """Test switch turn off method."""
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    state = hass.states.get(switch_entity_id)
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: switch_entity_id},
        blocking=True,
    )

    state = hass.states.get(switch_entity_id)
    assert state.state == STATE_OFF
