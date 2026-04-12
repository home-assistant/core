"""Tests for Victron GX MQTT device trackers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

from victron_mqtt import GpsLocation, Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.components.victron_gx.device_tracker import VictronDeviceTracker
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from .const import MOCK_INSTALLATION_ID

from tests.common import MockConfigEntry


async def test_victron_device_tracker(
    hass: HomeAssistant,
    init_integration: tuple[VictronVenusHub, MockConfigEntry],
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test DEVICE_TRACKER MetricKind - GPS location tracker is created and updated."""
    victron_hub, mock_config_entry = init_integration

    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Position/Latitude",
        '{"value": 52.1}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Position/Longitude",
        '{"value": 4.3}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.entity_id == "device_tracker.gps_location"
    assert entity.unique_id == f"{MOCK_INSTALLATION_ID}_gps_0_gps_location"
    assert entity.translation_key == "gps_location"

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["source_type"] == "gps"
    assert state.attributes["latitude"] == 52.1
    assert state.attributes["longitude"] == 4.3

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_gps_0")}
    )
    assert device is not None
    assert device.manufacturer == "Victron Energy"
    assert device.name == "GPS"

    # Update the metric to exercise the entity update callback path.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Position/Longitude",
        '{"value": 4.4}',
    )
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes["latitude"] == 52.1
    assert state.attributes["longitude"] == 4.4


def test_device_tracker_non_gps_updates_are_ignored() -> None:
    """Test non-GpsLocation values do not update coordinates or write state."""
    metric = SimpleNamespace(
        value="not_a_gps_location",
        unique_id="gps_0_gps_location",
        precision=None,
        main_topic=False,
        generic_short_id="gps_location",
        key_values={},
    )
    entity = VictronDeviceTracker(
        cast(Any, object()),
        cast(Any, metric),
        DeviceInfo(identifiers={(DOMAIN, f"{MOCK_INSTALLATION_ID}_gps_0")}),
        MOCK_INSTALLATION_ID,
    )

    assert entity.latitude is None
    assert entity.longitude is None

    with patch.object(entity, "async_write_ha_state") as mock_write_state:
        entity._on_update_cb("still_not_a_gps_location")

    assert entity.latitude is None
    assert entity.longitude is None
    mock_write_state.assert_not_called()

    with patch.object(entity, "async_write_ha_state") as mock_write_state:
        entity._on_update_cb(GpsLocation(latitude=1.5, longitude=2.5))

    assert entity.latitude == 1.5
    assert entity.longitude == 2.5
    mock_write_state.assert_called_once()
