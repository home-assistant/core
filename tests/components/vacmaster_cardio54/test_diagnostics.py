"""Tests for the diagnostics provided by the Vacmaster Cardio54 integration."""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_vacmaster_cardio54: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot config entry, entities and transmitter state.

    Mirrors the novy_cooker_hood diagnostics test (the reference RF-fan
    integration in HA core). Excludes only the runtime non-deterministic
    fields (registry IDs, timestamps) so the snapshot stays stable across
    runs and reorderings.
    """
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, init_vacmaster_cardio54
    )
    # Drop both runtime-generated values from the entry data so the snapshot
    # stays deterministic: the transmitter is a ULID HA picks at config-flow
    # time and the device_id is a random 20-bit number generated per entry.
    result["config_entry"]["data"].pop("transmitter")
    result["config_entry"]["data"].pop("device_id", None)

    assert result == snapshot(
        exclude=props(
            "config_entry_id",
            "context",
            "created_at",
            "device_id",
            "entry_id",
            "id",
            "last_changed",
            "last_reported",
            "last_updated",
            "modified_at",
            "unique_id",
        )
    )
