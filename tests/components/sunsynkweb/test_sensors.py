"""sensor tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Literal
from unittest.mock import AsyncMock

from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from tests.common import MockConfigEntry, async_fire_time_changed


async def next_tick(hass, freezer):
    """Make hass trigger the next update."""
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)  # noqa: F821
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_simple_update(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    init_integration: MockConfigEntry,
    freezer,
    sensor_keys: tuple[
        Literal["battery_power"],
        Literal["load_power"],
        Literal["grid_power"],
        Literal["pv_power"],
        Literal["state_of_charge"],
        Literal["acc_pv"],
        Literal["acc_load"],
        Literal["acc_grid_import"],
        Literal["acc_grid_export"],
        Literal["acc_battery_charge"],
        Literal["acc_battery_discharge"],
    ],
    snapshot: SnapshotAssertion,
) -> None:
    """Validate that all sensors are registered and that updates propagate."""
    for key in sensor_keys:
        state = hass.states.get(f"sensor.sunsynk_{key}")
        assert state.state == "unknown"

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)  # noqa: F821
    await hass.async_block_till_done(wait_background_tasks=True)
    for key in sensor_keys:
        state = hass.states.get(f"sensor.sunsynk_{key}")
        assert state.state == snapshot

    await next_tick(hass, freezer)
    for key in sensor_keys:
        state = hass.states.get(f"sensor.sunsynk_{key}")
        assert state.state == snapshot


async def test_bad_api_return_and_recovery(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    init_integration: MockConfigEntry,
    freezer,
    sensor_keys: tuple[
        Literal["battery_power"],
        Literal["load_power"],
        Literal["grid_power"],
        Literal["pv_power"],
        Literal["state_of_charge"],
        Literal["acc_pv"],
        Literal["acc_load"],
        Literal["acc_grid_import"],
        Literal["acc_grid_export"],
        Literal["acc_battery_charge"],
        Literal["acc_battery_discharge"],
    ],
    snapshot: SnapshotAssertion,
) -> None:
    """Verify that if api calls return invalid responses, all sensors are appropriately flagged as unavailable, then recover on normal updates."""
    coordinator = init_integration.runtime_data

    async def raisekeyerror():
        raise KeyError

    coordinator.cache.plants[0].update = raisekeyerror
    await next_tick(hass, freezer)
    for key in sensor_keys:
        state = hass.states.get(f"sensor.sunsynk_{key}")
        assert state.state == snapshot
    coordinator.cache.plants[0].update = AsyncMock()
    await next_tick(hass, freezer)
    for key in sensor_keys:
        state = hass.states.get(f"sensor.sunsynk_{key}")
        assert state.state == snapshot
