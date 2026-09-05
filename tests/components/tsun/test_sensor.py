"""Tests for TSUN sensors."""

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import LOGGER_SN

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_tsun_client: AsyncMock,
    entity_registry: EntityRegistry,
) -> None:
    """Test measurement entities and stable unique IDs."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get_entity_id(
        "sensor", "tsun", f"{LOGGER_SN}_ac_power"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    assert state.state == "1200.0"

    pv6 = entity_registry.async_get_entity_id(
        "sensor", "tsun", f"{LOGGER_SN}_pv6_energy_total"
    )
    assert pv6 is not None
    state = hass.states.get(pv6)
    assert state is not None
    assert state.state == "75.0"

    entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entries) == 37
