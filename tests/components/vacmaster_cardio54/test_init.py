"""Tests for the Vacmaster Cardio54 setup flow."""

from __future__ import annotations

from homeassistant.components.vacmaster_cardio54.const import (
    CONF_DEVICE_ID,
    CONF_TRANSMITTER,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_entry_retries_when_transmitter_missing(
    hass: HomeAssistant,
) -> None:
    """``async_setup_entry`` raises ``ConfigEntryNotReady`` if the configured
    transmitter registry id is gone, leaving the entry in the retry state."""
    fake_registry_id = "00000000000000000000000000"
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Vacmaster Cardio54",
        data={CONF_TRANSMITTER: fake_registry_id, CONF_DEVICE_ID: 0xABCDE},
        unique_id=f"{fake_registry_id}_ABCDE",
    )
    entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # ``ConfigEntryNotReady`` puts the entry into the SETUP_RETRY state and
    # HA will keep retrying on its own backoff schedule.
    assert entry.state is ConfigEntryState.SETUP_RETRY
