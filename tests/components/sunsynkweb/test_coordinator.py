"""Basic coordinator tests."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry


async def test_coordinator(
    hass: AsyncGenerator[HomeAssistant, None],
    basicdata: list,
    entity_registry: EntityRegistry,
    init_integration,
) -> None:
    """Run coordinator tests."""
    coordinator = init_integration.runtime_data
    battery_charge_state = hass.states.get("sensor.solar_battery_charge")
    assert battery_charge_state.state == "unknown"
    entity_registry.async_update_entity(battery_charge_state.entity_id)
    await coordinator.async_refresh()
    await hass.async_block_till_done(wait_background_tasks=True)
    assert battery_charge_state.state == "unknown"
