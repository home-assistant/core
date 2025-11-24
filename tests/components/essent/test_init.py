"""Integration tests for Essent setup and runtime."""

from __future__ import annotations

from essent_dynamic_pricing import (
    EssentConnectionError,
    EssentDataError,
    EssentError,
    EssentResponseError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.essent.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import async_fire_time_changed

pytestmark = [
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
]


async def test_full_integration_setup(hass: HomeAssistant) -> None:
    """Test complete integration setup and unload."""
    entry = await setup_integration(hass)
    ent_reg = er.async_get(hass)

    updated = False
    for unique_id in ("electricity_next_price", "gas_next_price"):
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        reg_entry = ent_reg.async_get(entity_id)
        assert reg_entry is not None
        if reg_entry.disabled_by:
            ent_reg.async_update_entity(entity_id, disabled_by=None)
            updated = True

    if updated:
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state == ConfigEntryState.LOADED

    def _state(unique_id: str) -> str | None:
        entity_id = ent_reg.async_get_entity_id("sensor", "essent", unique_id)
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        return state.state

    assert _state("electricity_current_price") is not None
    assert _state("electricity_next_price") is not None
    assert _state("gas_current_price") is not None
    assert _state("gas_next_price") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED


async def test_device_registry_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Ensure the integration registers a service device."""
    entry = await setup_integration(hass)

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    assert device_entry is not None
    assert device_entry.manufacturer == "Essent"
    assert device_entry.name == "Essent"
    assert device_entry.entry_type is dr.DeviceEntryType.SERVICE


@pytest.mark.parametrize(
    "side_effect",
    [
        EssentConnectionError("fail"),
        EssentResponseError("bad response"),
        EssentDataError("bad data"),
        EssentError("boom"),
    ],
)
async def test_setup_retries_on_client_errors(
    hass: HomeAssistant, patch_essent_client, side_effect: Exception
) -> None:
    """Ensure setup retries when the client raises."""
    patch_essent_client.async_get_prices.side_effect = side_effect

    entry = await setup_integration(hass)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_polling_interval_triggers_refresh(
    hass: HomeAssistant,
    patch_essent_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Coordinator should refresh data on the polling interval."""
    await setup_integration(hass)

    next_poll = dt_util.utcnow() + UPDATE_INTERVAL
    freezer.move_to(next_poll)
    async_fire_time_changed(hass, next_poll)
    await hass.async_block_till_done()

    assert patch_essent_client.async_get_prices.call_count == 2


async def test_disable_polling_skips_scheduled_refresh(
    hass: HomeAssistant,
    patch_essent_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Coordinator should not schedule refreshes when polling is disabled."""
    await setup_integration(hass, pref_disable_polling=True)

    future = dt_util.utcnow() + UPDATE_INTERVAL
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert patch_essent_client.async_get_prices.call_count == 1


async def test_shutdown_cancels_scheduled_updates(
    hass: HomeAssistant,
    patch_essent_client,
    freezer: FrozenDateTimeFactory,
) -> None:
    """API polling should stop once the entry is unloaded."""
    entry = await setup_integration(hass)
    assert patch_essent_client.async_get_prices.call_count == 1

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    future = dt_util.utcnow() + UPDATE_INTERVAL
    freezer.move_to(future)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert patch_essent_client.async_get_prices.call_count == 1
