"""Full integration tests for Essent."""

from __future__ import annotations

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

pytestmark = [
    pytest.mark.freeze_time("2025-11-16 10:30:00+01:00"),
    pytest.mark.usefixtures("disable_coordinator_schedules"),
]


async def test_full_integration_setup(
    hass: HomeAssistant, essent_api_response: dict
) -> None:
    """Test complete integration setup and unload."""
    entry = await setup_integration(hass, essent_api_response)
    ent_reg = er.async_get(hass)

    updated = False
    for unique_id in ("essent_electricity_next_price", "essent_gas_next_price"):
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

    assert _state("essent_electricity_current_price") is not None
    assert _state("essent_electricity_next_price") is not None
    assert _state("essent_gas_current_price") is not None
    assert _state("essent_gas_next_price") is not None

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state == ConfigEntryState.NOT_LOADED
