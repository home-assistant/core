"""Tests for the VRM Forecasts sensors.

Consolidates most per-sensor assertions into snapshot-based regression tests.
"""

from __future__ import annotations

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.victron_remote_monitoring.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import (
    CONST_FORECAST_RECORDS,  # noqa: F401 (kept for potential future targeted assertions)
)


async def test_unique_ids(
    hass: HomeAssistant, init_integration, mock_config_entry
) -> None:
    """Ensure unique_id format includes key and site id."""
    ent_reg = er.async_get(hass)
    site_id = mock_config_entry.data["site_id"]

    # Check a couple of representative sensors
    for key in (
        "energy_production_estimate_today",
        "consumption_highest_peak_time_today",
    ):
        unique_id = f"{site_id}|{key}"
        entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, unique_id)
        assert entity_id is not None, key
        entity = ent_reg.async_get(entity_id)
        assert entity is not None, entity_id
        assert entity.unique_id == unique_id


async def test_sensors_snapshot(
    hass: HomeAssistant,
    init_integration,
    mock_config_entry,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot all VRM sensor states & key attributes."""
    ent_reg = er.async_get(hass)
    site_id = mock_config_entry.data["site_id"]
    collected: dict[str, dict] = {}
    for entry in ent_reg.entities.values():
        if entry.platform != DOMAIN:
            continue
        if not entry.unique_id.startswith(f"{site_id}|"):
            continue
        state_obj = hass.states.get(entry.entity_id)
        assert state_obj is not None, entry.entity_id
        attrs = state_obj.attributes
        collected[entry.unique_id] = {
            "entity_id": entry.entity_id,
            "state": state_obj.state,
            "device_class": attrs.get("device_class"),
            "state_class": attrs.get("state_class"),
            "unit_of_measurement": attrs.get("unit_of_measurement"),
            "suggested_display_precision": attrs.get("suggested_display_precision"),
        }
    collected = dict(sorted(collected.items()))
    assert collected == snapshot
