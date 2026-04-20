"""Tests for Victron GX MQTT device trackers."""

from __future__ import annotations

from victron_mqtt import Hub as VictronVenusHub
from victron_mqtt.testing import finalize_injection, inject_message

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.victron_gx.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

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
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Fix",
        '{"value": 1}',
    )
    await finalize_injection(victron_hub, False)
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
    assert state.attributes == {
        "source_type": SourceType.GPS,
        "latitude": 52.1,
        "longitude": 4.3,
        "gps_accuracy": 0,
        "friendly_name": "GPS Location",
        "in_zones": [],
    }

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
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Altitude",
        '{"value": 11.0}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Course",
        '{"value": 180.0}',
    )
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Speed",
        '{"value": 3.5}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes == {
        "source_type": SourceType.GPS,
        "latitude": 52.1,
        "longitude": 4.4,
        "gps_accuracy": 0,
        "friendly_name": "GPS Location",
        "in_zones": [],
    }

    # Send GPS fix lost to exercise the non-GpsLocation reset branch.
    await inject_message(
        victron_hub,
        f"N/{MOCK_INSTALLATION_ID}/gps/0/Fix",
        '{"value": 0}',
    )
    await finalize_injection(victron_hub)
    await hass.async_block_till_done()

    state = hass.states.get(entity.entity_id)
    assert state is not None
    assert state.attributes == {
        "source_type": SourceType.GPS,
        "friendly_name": "GPS Location",
        "in_zones": [],
    }
