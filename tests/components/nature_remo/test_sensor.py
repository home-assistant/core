"""Tests for the Nature Remo sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aionatureremo import Appliance, Device, NatureRemoConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import DATA_INSTANCES
from homeassistant.util import dt as dt_util

from .conftest import load_json_fixture

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Snapshot every entity and registry entry the integration creates."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


async def test_sensors_unavailable_on_update_failure(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A failed poll marks sensors unavailable."""
    mock_client.get_devices.side_effect = NatureRemoConnectionError("refused")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_offline_device_sensors_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
) -> None:
    """A hub reporting online=False serves no readings; None keeps serving.

    ``online`` only exists on newer firmware, so the Remo mini fixture
    (no flag at all, parsed as None) must stay available.
    """
    mock_client.get_devices.return_value = [
        replace(device, online=False) if device.id == "device-remo3-1" else device
        for device in devices
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.living_remo_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.living_remo_humidity").state == STATE_UNAVAILABLE

    mini = hass.states.get("sensor.bedroom_remo_mini_temperature")
    assert mini is not None
    assert mini.state != STATE_UNAVAILABLE


async def test_sensor_reads_after_the_device_vanishes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A hub gone from the coordinator data never raises a bare KeyError.

    The devices dict can lose the hub while reads still reach the entity,
    because the poll that drops it notifies the listeners after the data is
    swapped in.
    """
    entity = hass.data[DATA_INSTANCES][SENSOR_DOMAIN].get_entity(
        "sensor.living_remo_temperature"
    )
    assert entity is not None
    coordinator = init_integration.runtime_data
    coordinator.data.devices.pop("device-remo3-1")

    assert entity.device.id == "device-remo3-1"  # last-known snapshot
    entity.async_write_ha_state()
    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_smart_meter_without_reverse_direction(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """A meter without EPC 227 (no solar) gets no sold-energy sensor."""
    payloads = load_json_fixture("appliances.json")
    for payload in payloads:
        if payload["id"] == "appliance-meter-1":
            payload["smart_meter"]["echonetlite_properties"] = [
                prop
                for prop in payload["smart_meter"]["echonetlite_properties"]
                if prop["epc"] != 227
            ]
    mock_client.get_appliances.return_value = [
        Appliance.from_dict(item) for item in payloads
    ]

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.smart_meter_purchased_energy") is not None
    assert hass.states.get("sensor.smart_meter_sold_energy") is None
