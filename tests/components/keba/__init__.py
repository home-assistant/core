"""Tests for the KEBA charging station integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.keba.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


def snapshot_keba_platform(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    domain: str,
) -> None:
    """Snapshot the registry entries and states of one KEBA platform.

    The integration is set up from YAML, so its entities have no config entry
    and pytest_homeassistant.common.snapshot_platform cannot find them.
    """
    entries = sorted(
        (
            entry
            for entry in entity_registry.entities.values()
            if entry.platform == DOMAIN and entry.domain == domain
        ),
        key=lambda entry: entry.entity_id,
    )
    assert entries
    for entry in entries:
        assert entry == snapshot(name=f"{entry.entity_id}-entry")
        state = hass.states.get(entry.entity_id)
        assert state, f"State not found for {entry.entity_id}"
        assert state == snapshot(name=f"{entry.entity_id}-state")
