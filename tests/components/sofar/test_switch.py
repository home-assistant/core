"""Test the Sofar Inverter Modbus switch platform."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sofar.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.sofar.coordinator import _SLOW_TIER_EVERY_N_CYCLES
from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_active_power_control_switch_state_and_staging(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the switch reflects live state and stages rather than writes."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "sofar", f"{MOCK_SERIAL}_active_power_control_enabled"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF

    coordinator = init_integration.runtime_data

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert coordinator.pending["active_power_control_enabled"] is True
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    assert coordinator.pending["active_power_control_enabled"] is False
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_OFF


async def test_active_power_control_switch_unique_id_and_device(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the switch attaches to the inverter's device with its unique_id."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "sofar", f"{MOCK_SERIAL}_active_power_control_enabled"
    )
    assert entity_id is not None
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None
    assert entity_entry.unique_id == f"{MOCK_SERIAL}_active_power_control_enabled"
    assert entity_entry.device_id is not None


async def test_active_power_control_switch_unavailable_on_component_failure(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test the switch goes unavailable on component failure, and recovers."""
    entity_id = entity_registry.async_get_entity_id(
        SWITCH_DOMAIN, "sofar", f"{MOCK_SERIAL}_active_power_control_enabled"
    )
    assert entity_id is not None

    coordinator = init_integration.runtime_data
    unit = coordinator.connection.for_unit(1)
    unit.fail_read(0x1105, IllegalDataAddressError())

    # active_power_control is settings-tier: it's only polled once every
    # _SLOW_TIER_EVERY_N_CYCLES, so stop right on that cycle to observe it.
    for _ in range(_SLOW_TIER_EVERY_N_CYCLES - 1):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    unit.fail_read(0x1105, None)
    for _ in range(_SLOW_TIER_EVERY_N_CYCLES):
        freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE
