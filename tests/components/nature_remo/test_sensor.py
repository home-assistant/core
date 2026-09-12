"""Tests for the Nature Remo sensor platform."""

from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock

from aionatureremo import Appliance, Device, NatureRemoConnectionError
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import async_poll, load_json_fixture

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


async def test_sensors_unavailable_when_the_hub_disappears(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
) -> None:
    """A hub the API stops reporting leaves its sensors unavailable."""
    mock_client.get_devices.return_value = [
        device for device in devices if device.id != "device-remo3-1"
    ]
    await async_poll(hass)

    state = hass.states.get("sensor.living_remo_temperature")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_smart_meter_follows_the_hub_reading_it(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
) -> None:
    """A meter goes unavailable while its Remo E reports itself offline.

    The cloud keeps serving the readings it collected before the hub went
    away, so without following the hub the meter would look live with
    stale values.
    """
    assert hass.states.get("sensor.smart_meter_power").state != STATE_UNAVAILABLE

    mock_client.get_devices.return_value = [
        replace(device, online=False) if device.id == "device-remoe-1" else device
        for device in devices
    ]
    await async_poll(hass)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNAVAILABLE


async def test_smart_meter_unavailable_when_its_hub_disappears(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    devices: list[Device],
) -> None:
    """A meter whose hub drops out of the account stops reporting.

    The appliance keeps its cached readings in the API response, so
    without following the hub the meter would look live.
    """
    mock_client.get_devices.return_value = [
        device for device in devices if device.id != "device-remoe-1"
    ]
    await async_poll(hass)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNAVAILABLE


async def test_smart_meter_reading_dropout_is_unknown(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_client: AsyncMock,
    appliances: list[Appliance],
) -> None:
    """A meter that stops publishing properties reads unknown, not stale."""
    mock_client.get_appliances.return_value = [
        replace(appliance, smart_meter=None)
        if appliance.id == "appliance-meter-1"
        else appliance
        for appliance in appliances
    ]
    await async_poll(hass)

    assert hass.states.get("sensor.smart_meter_power").state == STATE_UNKNOWN


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

    assert hass.states.get("sensor.smart_meter_imported_energy") is not None
    assert hass.states.get("sensor.smart_meter_exported_energy") is None
