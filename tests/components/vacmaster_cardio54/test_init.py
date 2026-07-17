"""Tests for the Vacmaster Cardio54 setup and unload."""

from __future__ import annotations

from homeassistant.components.vacmaster_cardio54.const import (
    CONF_DEVICE_ID,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    init_vacmaster_cardio54: MockConfigEntry,
) -> None:
    """The config entry sets up and unloads cleanly."""
    entry = init_vacmaster_cardio54
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_with_missing_transmitter_marks_fan_unavailable(
    hass: HomeAssistant,
) -> None:
    """Setup succeeds without the transmitter; the fan is unavailable.

    When the configured transmitter has been removed from the entity
    registry the entry still loads (there is no device to contact), and
    the fan entity marks itself unavailable instead of failing setup.
    """
    fake_registry_id = "00000000000000000000000000"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Vacmaster Cardio54",
        data={CONF_TRANSMITTER: fake_registry_id, CONF_DEVICE_ID: 0xABCDE},
        unique_id=f"{fake_registry_id}_ABCDE",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    state = hass.states.get("fan.vacmaster_cardio54")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
