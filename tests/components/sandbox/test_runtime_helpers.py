"""Helper setup through a real sandbox worker."""

import asyncio

import pytest

from homeassistant.components.sandbox import async_setup_runtime
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import entity_sources


@pytest.mark.parametrize("entity_type", [Platform.SENSOR, Platform.BINARY_SENSOR])
async def test_random_helper(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_type: Platform
) -> None:
    """A helper stays loaded and exposes its source integration to the UI."""
    await hass.async_start()
    await async_setup_runtime(hass, domains=frozenset({"random"}))
    try:
        result = await hass.config_entries.flow.async_init(
            "random", context={"source": SOURCE_USER}
        )
        assert result["type"] is FlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": entity_type}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Worker random"}
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
        entry = result["result"]
        assert entry.state is ConfigEntryState.LOADED
        async with asyncio.timeout(5):
            while not (
                entities := er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                )
            ):
                await asyncio.sleep(0.01)
        assert len(entities) == 1
        entity = entities[0]
        state = hass.states.get(entity.entity_id)
        assert state is not None
        assert state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        assert entity.platform == "random"
        assert entity.unique_id == entry.entry_id
        assert entity_sources(hass)[entity.entity_id] == {
            "domain": "random",
            "config_entry": entry.entry_id,
        }
    finally:
        for entry in hass.config_entries.async_entries("random"):
            await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_stop(force=True)
